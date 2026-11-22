from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("cryptography")

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.api_support import make_client, register, upload  # noqa: E402


class FakeGoogle:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.upload_body: dict[str, Any] | None = None
        self.uploaded_bytes = 0
        self.refreshes = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        self.calls.append(f"{request.method} {url.host}{url.path}")
        if url.host == "oauth2.googleapis.com":
            form = parse_qs(request.content.decode())
            if form["grant_type"] == ["authorization_code"]:
                assert form["code"] == ["good-code"]
                return httpx.Response(
                    200,
                    json={
                        "access_token": "at-1",
                        "refresh_token": "rt-1",
                        "expires_in": 3600,
                    },
                )
            self.refreshes += 1
            assert form["refresh_token"] == ["rt-1"]
            return httpx.Response(
                200, json={"access_token": "at-2", "expires_in": 3600}
            )
        if url.path.endswith("/channels"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "UC123",
                            "snippet": {"title": "My Channel"},
                            "contentDetails": {
                                "relatedPlaylists": {"uploads": "UU123"}
                            },
                        }
                    ]
                },
            )
        if url.path.endswith("/playlistItems"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "snippet": {
                                "title": "My long talk",
                                "channelId": "UC123",
                                "publishedAt": "2026-01-01T00:00:00Z",
                            },
                            "contentDetails": {"videoId": "vid-own"},
                        }
                    ]
                },
            )
        if url.path.endswith("/videos") and request.method == "GET":
            video_id = url.params["id"]
            channel = "UC123" if video_id == "vid-own" else "UC-someone-else"
            return httpx.Response(
                200,
                json={"items": [{"snippet": {"title": "x", "channelId": channel}}]},
            )
        if url.host == "www.googleapis.com" and url.path.startswith("/upload/"):
            assert request.headers["authorization"].startswith("Bearer ")
            self.upload_body = json.loads(request.content)
            return httpx.Response(
                200, headers={"location": "https://upload.example/session-1"}
            )
        if url.host == "upload.example":
            self.uploaded_bytes = len(request.content)
            return httpx.Response(200, json={"id": "yt-789"})
        return httpx.Response(404, json={"error": str(url)})


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> FakeGoogle:
    fake = FakeGoogle()
    from snipzo.api import youtube

    monkeypatch.setattr(
        youtube,
        "http_client_factory",
        lambda: httpx.Client(transport=httpx.MockTransport(fake.handler)),
    )
    return fake


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, google: FakeGoogle
) -> Iterator[TestClient]:
    monkeypatch.setenv("SNIPZO_GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("SNIPZO_GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("SNIPZO_WEB_APP_URL", "http://web.test")
    yield from make_client(tmp_path, monkeypatch)


def _connect(client: TestClient, headers: dict[str, str]) -> str:
    response = client.get("/youtube/connect", headers=headers)
    assert response.status_code == 200, response.text
    auth_url = response.json()["auth_url"]
    query = parse_qs(urlparse(auth_url).query)
    assert query["access_type"] == ["offline"]
    assert "youtube.upload" in query["scope"][0]
    state = query["state"][0]
    callback = client.get(
        "/youtube/callback",
        params={"state": state, "code": "good-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 303, callback.text
    assert callback.headers["location"] == "http://web.test/channels?connected=1"
    status = client.get("/youtube/status", headers=headers).json()
    assert status["configured"] is True
    assert status["channels"][0]["external_id"] == "UC123"
    return str(status["channels"][0]["id"])


def test_connect_stores_encrypted_tokens(client: TestClient) -> None:
    headers = register(client)
    channel_id = _connect(client, headers)

    from snipzo.api.db import session_scope
    from snipzo.api.tables import Channel

    with session_scope() as session:
        channel = session.get(Channel, channel_id)
        assert channel is not None
        assert channel.access_token_enc and "at-1" not in channel.access_token_enc
        assert channel.refresh_token_enc and "rt-1" not in channel.refresh_token_enc


def test_callback_rejects_bad_state(client: TestClient) -> None:
    response = client.get(
        "/youtube/callback", params={"state": "forged.state", "code": "good-code"}
    )
    assert response.status_code == 400


def test_connect_requires_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SNIPZO_GOOGLE_CLIENT_ID", raising=False)
    for test_client in make_client(tmp_path, monkeypatch):
        headers = register(test_client)
        assert test_client.get("/youtube/connect", headers=headers).status_code == 503


def test_list_and_import_only_owned_videos(client: TestClient) -> None:
    headers = register(client)
    channel_id = _connect(client, headers)
    videos = client.get(f"/youtube/channels/{channel_id}/videos", headers=headers)
    assert videos.status_code == 200, videos.text
    assert [item["id"] for item in videos.json()] == ["vid-own"]

    no_rights = client.post(
        f"/youtube/channels/{channel_id}/import",
        headers=headers,
        json={"video_id": "vid-own"},
    )
    assert no_rights.status_code == 400
    foreign = client.post(
        f"/youtube/channels/{channel_id}/import",
        headers=headers,
        json={"video_id": "vid-foreign", "rights_confirmed": True},
    )
    assert foreign.status_code == 403
    owned = client.post(
        f"/youtube/channels/{channel_id}/import",
        headers=headers,
        json={"video_id": "vid-own", "rights_confirmed": True},
    )
    # The Data API has no media download; this stays off unless yt-dlp is enabled.
    assert owned.status_code == 501
    assert "Ownership verified" in owned.json()["detail"]

    other = register(client, "b@example.com")
    assert (
        client.get(f"/youtube/channels/{channel_id}/videos", headers=other).status_code
        == 404
    )


def test_publish_uploads_with_disclosure_and_schedule(
    client: TestClient,
    google: FakeGoogle,
    sample_video_factory: Callable[..., Path],
) -> None:
    headers = register(client)
    channel_id = _connect(client, headers)
    project = upload(client, headers, sample_video_factory(name="t.mp4", duration=4.0))
    clip = client.get(f"/projects/{project['id']}", headers=headers).json()["clips"][0]
    url = f"/projects/{project['id']}/clips/{clip['clip_id']}/publish"

    missing_rights = client.post(url, headers=headers, json={"channel_id": channel_id})
    assert missing_rights.status_code == 400
    too_soon = client.post(
        url,
        headers=headers,
        json={
            "channel_id": channel_id,
            "rights_confirmed": True,
            "publish_at": datetime.now(UTC).isoformat(),
        },
    )
    assert too_soon.status_code == 422

    when = datetime.now(UTC) + timedelta(days=1)
    response = client.post(
        url,
        headers=headers,
        json={
            "channel_id": channel_id,
            "rights_confirmed": True,
            "title": "My Short",
            "privacy_status": "public",
            "publish_at": when.isoformat(),
            "contains_synthetic_media": True,
        },
    )
    assert response.status_code == 201, response.text
    publications = client.get(
        f"/projects/{project['id']}/publications", headers=headers
    ).json()
    assert publications[0]["status"] == "scheduled", publications
    assert publications[0]["external_id"] == "yt-789"
    assert publications[0]["url"] == "https://youtube.com/shorts/yt-789"
    body = google.upload_body
    assert body is not None
    assert body["snippet"]["title"] == "My Short"
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["containsSyntheticMedia"] is True
    assert body["status"]["publishAt"].endswith("Z")
    assert google.uploaded_bytes > 1000


def test_expired_token_is_refreshed(client: TestClient, google: FakeGoogle) -> None:
    headers = register(client)
    channel_id = _connect(client, headers)
    from snipzo.api.db import session_scope
    from snipzo.api.tables import Channel

    with session_scope() as session:
        channel = session.get(Channel, channel_id)
        assert channel is not None
        channel.token_expires_at = datetime.now(UTC) - timedelta(minutes=5)
    response = client.get(f"/youtube/channels/{channel_id}/videos", headers=headers)
    assert response.status_code == 200
    assert google.refreshes == 1


def test_build_status_without_schedule() -> None:
    from snipzo.api.youtube import build_status

    status = build_status(
        privacy_status="unlisted",
        publish_at=None,
        made_for_kids=False,
        contains_synthetic_media=False,
    )
    assert status == {
        "privacyStatus": "unlisted",
        "selfDeclaredMadeForKids": False,
        "containsSyntheticMedia": False,
    }


def test_takedown_request(client: TestClient) -> None:
    bad = client.post(
        "/takedown",
        json={
            "reporter_name": "Owner",
            "reporter_email": "owner@example.com",
            "content_url": "https://youtube.com/shorts/x",
            "details": "This is my copyrighted interview.",
        },
    )
    assert bad.status_code == 400
    ok = client.post(
        "/takedown",
        json={
            "reporter_name": "Owner",
            "reporter_email": "owner@example.com",
            "content_url": "https://youtube.com/shorts/x",
            "details": "This is my copyrighted interview.",
            "good_faith": True,
        },
    )
    assert ok.status_code == 201
    assert ok.json()["status"] == "received"
