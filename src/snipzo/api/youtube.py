"""YouTube Data API: OAuth, channel lookup, owned-video listing, and uploads."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from snipzo.api.settings import ApiSettings
from snipzo.errors import SnipzoError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/youtube/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
)

# Tests swap this for an httpx.Client backed by httpx.MockTransport.
HttpClientFactory = Callable[[], httpx.Client]
http_client_factory: HttpClientFactory = lambda: httpx.Client(timeout=120.0)  # noqa: E731


class YouTubeError(SnipzoError):
    """A YouTube or Google OAuth request failed."""


class TokenCipher:
    """Encrypts OAuth tokens at rest with Fernet (AES-128-CBC + HMAC)."""

    def __init__(self, key: str | None, fallback_secret: str) -> None:
        from cryptography.fernet import Fernet

        if key:
            material = key.encode()
        else:
            digest = hashlib.sha256(
                f"snipzo-tokens:{fallback_secret}".encode()
            ).digest()
            material = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(material)

    @classmethod
    def from_settings(cls, settings: ApiSettings) -> TokenCipher:
        return cls(settings.token_encryption_key, settings.secret_key)

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.decrypt(value.encode()).decode()


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime


@dataclass(frozen=True)
class ChannelInfo:
    id: str
    title: str
    uploads_playlist: str | None


@dataclass(frozen=True)
class VideoInfo:
    id: str
    title: str
    channel_id: str
    published_at: str | None
    thumbnail: str | None


def is_configured(settings: ApiSettings) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def authorization_url(settings: ApiSettings, state: str) -> str:
    if not is_configured(settings):
        raise YouTubeError(
            "YouTube is not configured. Set SNIPZO_GOOGLE_CLIENT_ID and "
            "SNIPZO_GOOGLE_CLIENT_SECRET."
        )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


class YouTubeClient:
    """Thin wrapper over the Google OAuth and YouTube Data API v3 endpoints."""

    def __init__(self, settings: ApiSettings, http: httpx.Client | None = None) -> None:
        self.settings = settings
        self.http = http or http_client_factory()

    def _check(self, response: httpx.Response, what: str) -> dict[str, Any]:
        if response.status_code >= 400:
            detail = response.text[:300]
            raise YouTubeError(f"{what} failed ({response.status_code}): {detail}")
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict):
            raise YouTubeError(f"{what} returned an unexpected response.")
        return payload

    def _tokens(self, payload: dict[str, Any], refresh: str | None) -> OAuthTokens:
        expires = datetime.now(UTC) + timedelta(
            seconds=int(payload.get("expires_in", 3600)) - 60
        )
        return OAuthTokens(
            access_token=str(payload["access_token"]),
            refresh_token=payload.get("refresh_token") or refresh,
            expires_at=expires,
        )

    def exchange_code(self, code: str) -> OAuthTokens:
        response = self.http.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "redirect_uri": self.settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        return self._tokens(self._check(response, "Token exchange"), None)

    def refresh(self, refresh_token: str) -> OAuthTokens:
        response = self.http.post(
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
        return self._tokens(self._check(response, "Token refresh"), refresh_token)

    def _get(self, access: str, path: str, params: dict[str, str]) -> dict[str, Any]:
        response = self.http.get(
            f"{API_URL}/{path}",
            params=params,
            headers={"Authorization": f"Bearer {access}"},
        )
        return self._check(response, f"YouTube {path}")

    def my_channel(self, access: str) -> ChannelInfo:
        payload = self._get(
            access, "channels", {"part": "snippet,contentDetails", "mine": "true"}
        )
        items = payload.get("items") or []
        if not items:
            raise YouTubeError("This Google account has no YouTube channel.")
        item = items[0]
        uploads = (
            item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        )
        return ChannelInfo(
            id=str(item["id"]),
            title=str(item.get("snippet", {}).get("title", "")),
            uploads_playlist=uploads,
        )

    def list_uploads(
        self, access: str, playlist_id: str, limit: int = 25
    ) -> list[VideoInfo]:
        payload = self._get(
            access,
            "playlistItems",
            {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": str(min(limit, 50)),
            },
        )
        videos: list[VideoInfo] = []
        for item in payload.get("items") or []:
            snippet = item.get("snippet", {})
            video_id = item.get("contentDetails", {}).get("videoId") or snippet.get(
                "resourceId", {}
            ).get("videoId")
            if not video_id:
                continue
            thumbs = snippet.get("thumbnails", {})
            thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
            videos.append(
                VideoInfo(
                    id=str(video_id),
                    title=str(snippet.get("title", "")),
                    channel_id=str(snippet.get("channelId", "")),
                    published_at=snippet.get("publishedAt"),
                    thumbnail=thumb,
                )
            )
        return videos

    def get_video(self, access: str, video_id: str) -> VideoInfo | None:
        payload = self._get(access, "videos", {"part": "snippet", "id": video_id})
        items = payload.get("items") or []
        if not items:
            return None
        snippet = items[0].get("snippet", {})
        return VideoInfo(
            id=video_id,
            title=str(snippet.get("title", "")),
            channel_id=str(snippet.get("channelId", "")),
            published_at=snippet.get("publishedAt"),
            thumbnail=None,
        )

    def upload_video(
        self,
        access: str,
        path: Path,
        *,
        snippet: dict[str, Any],
        status: dict[str, Any],
    ) -> str:
        """Resumable upload (`videos.insert`); returns the new video id."""
        size = path.stat().st_size
        start = self.http.post(
            UPLOAD_URL,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(size),
            },
            content=json.dumps({"snippet": snippet, "status": status}).encode(),
        )
        if start.status_code >= 400:
            raise YouTubeError(
                f"Upload start failed ({start.status_code}): {start.text[:300]}"
            )
        location = start.headers.get("location")
        if not location:
            raise YouTubeError("Upload start did not return an upload URL.")
        with path.open("rb") as handle:
            done = self.http.put(
                location,
                headers={
                    "Authorization": f"Bearer {access}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(size),
                },
                content=handle.read(),
            )
        payload = self._check(done, "Video upload")
        video_id = payload.get("id")
        if not video_id:
            raise YouTubeError("Upload finished without a video id.")
        return str(video_id)


def build_status(
    *,
    privacy_status: str,
    publish_at: datetime | None,
    made_for_kids: bool,
    contains_synthetic_media: bool,
) -> dict[str, Any]:
    """`status` for videos.insert, including the altered/synthetic disclosure."""
    status: dict[str, Any] = {
        "privacyStatus": privacy_status,
        "selfDeclaredMadeForKids": made_for_kids,
        "containsSyntheticMedia": contains_synthetic_media,
    }
    if publish_at is not None:
        status["privacyStatus"] = "private"  # required by YouTube for scheduling
        status["publishAt"] = publish_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return status
