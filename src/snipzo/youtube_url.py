"""Parse and normalise YouTube video URLs (no network)."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from snipzo.errors import SnipzoError

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_YOUTUBE_ROOTS = {"youtube.com", "youtu.be", "youtube-nocookie.com"}
_SOCIAL_ROOTS = {"tiktok.com", "instagram.com"}


class YoutubeUrlError(SnipzoError):
    """The pasted URL is not a usable single-video YouTube link."""


def _root_host(host: str) -> str:
    host = host.lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def is_youtube_host(host: str) -> bool:
    root = _root_host(host)
    return root in _YOUTUBE_ROOTS or any(
        root.endswith("." + item) for item in _YOUTUBE_ROOTS
    )


def is_blocked_social_host(host: str) -> bool:
    root = _root_host(host)
    return root in _SOCIAL_ROOTS or any(
        root.endswith("." + item) for item in _SOCIAL_ROOTS
    )


def _video_id(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip()
    return token if VIDEO_ID_RE.match(token) else None


def parse_youtube_video_id(url: str) -> str:
    """Return the 11-character video id, or raise a friendly ``YoutubeUrlError``."""
    raw = url.strip()
    if not raw:
        raise YoutubeUrlError("Paste a YouTube link or a direct link to a video file.")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise YoutubeUrlError("Source URL must be an http(s) link.")
    host = parsed.netloc
    if is_blocked_social_host(host):
        raise YoutubeUrlError(
            "TikTok and Instagram links aren't supported yet. "
            "Upload the file, or paste a YouTube or direct video link."
        )
    if not is_youtube_host(host):
        raise YoutubeUrlError("not-youtube")

    path = unquote(parsed.path or "").rstrip("/")
    query = parse_qs(parsed.query, keep_blank_values=True)
    root = _root_host(host)

    if root == "youtu.be":
        first = path.lstrip("/").split("/", 1)[0] if path else ""
        video_id = _video_id(first)
        if video_id:
            return video_id
        raise YoutubeUrlError("That YouTube link is missing a video id.")

    parts = [part for part in path.split("/") if part]

    if path == "/watch" or (parts and parts[0] == "watch" and len(parts) == 1):
        values = query.get("v") or []
        video_id = _video_id(values[0] if values else None)
        if video_id:
            return video_id
        if query.get("list"):
            raise YoutubeUrlError("Paste a link to a single video, not a playlist.")
        raise YoutubeUrlError("That YouTube link is missing a video id.")

    if parts and parts[0] == "playlist":
        raise YoutubeUrlError("Paste a link to a single video, not a playlist.")

    if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed", "v", "e"}:
        video_id = _video_id(parts[1].split("?", 1)[0])
        if video_id:
            return video_id
        raise YoutubeUrlError("That YouTube link is missing a video id.")

    if len(parts) == 2 and parts[0] == "watch":
        video_id = _video_id(parts[1])
        if video_id:
            return video_id

    if parts:
        first = parts[0]
        channel_page = first in {"channel", "c", "user", "feed", "results", "hashtag"}
        if channel_page or first.startswith("@"):
            raise YoutubeUrlError(
                "Paste a link to a single YouTube video, not a channel or playlist."
            )

    raise YoutubeUrlError(
        "Paste a link to a single YouTube video (watch, Shorts, youtu.be, or embed)."
    )


def canonical_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def default_thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def classify_source_url(url: str) -> tuple[str, str]:
    """Return ``("youtube", canonical_watch_url)`` or ``("url", stripped)``.

    Raises ``YoutubeUrlError`` / ``SnipzoError`` for blocked or invalid links.
    """
    raw = url.strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SnipzoError("Source URL must be an http(s) link to a video file.")
    host = parsed.netloc
    if is_blocked_social_host(host):
        raise YoutubeUrlError(
            "TikTok and Instagram links aren't supported yet. "
            "Upload the file, or paste a YouTube or direct video link."
        )
    if is_youtube_host(host):
        video_id = parse_youtube_video_id(raw)
        return "youtube", canonical_watch_url(video_id)
    return "url", raw
