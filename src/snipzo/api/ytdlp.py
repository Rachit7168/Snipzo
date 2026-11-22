"""yt-dlp probe and download for YouTube URL imports.

Tests replace ``downloader_factory`` so CI never talks to the network.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from snipzo.api.settings import ApiSettings, get_api_settings
from snipzo.errors import SnipzoError
from snipzo.youtube_url import (
    canonical_watch_url,
    default_thumbnail_url,
    parse_youtube_video_id,
)

log = logging.getLogger(__name__)

# Prefer mp4 video + m4a audio, merged to mp4, never above 1080p.
YOUTUBE_FORMAT = (
    "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
    "bestvideo[height<=1080]+bestaudio/"
    "best[height<=1080][ext=mp4]/"
    "best[height<=1080]"
)

GENERIC_DOWNLOAD_ERROR = (
    "Couldn't download this YouTube video. Try again, or upload the file instead."
)


class YoutubeUnavailable(SnipzoError):
    """User-facing reason a YouTube video cannot be imported."""


@dataclass(frozen=True)
class YoutubeVideoInfo:
    video_id: str
    title: str
    duration: float | None
    thumbnail_url: str | None
    url: str


class YoutubeDownloader(Protocol):
    def probe(self, url: str) -> YoutubeVideoInfo:
        """Return metadata without downloading the media file."""

    def download(
        self, url: str, dest: Path, *, max_bytes: int, timeout: int
    ) -> Path:
        """Download at most 1080p into ``dest`` (an .mp4 path)."""


def friendly_restriction(info: dict[str, Any]) -> str | None:
    """Map yt-dlp metadata to a short user-facing rejection, or None if allowed."""
    kind = str(info.get("_type") or "video")
    if kind == "playlist":
        return "Paste a link to a single video, not a playlist."
    availability = str(info.get("availability") or "").lower()
    live_status = str(info.get("live_status") or "").lower()
    try:
        age_limit = int(info.get("age_limit") or 0)
    except (TypeError, ValueError):
        age_limit = 0
    is_live = bool(info.get("is_live"))

    if availability == "private":
        return "This video is private, so Snipzo can't import it."
    if availability == "subscriber_only":
        return "This video is members-only, so Snipzo can't import it."
    if availability == "premium":
        return "This video requires YouTube Premium, so Snipzo can't import it."
    if availability in {"needs_auth", "unlisted"}:
        # Unlisted is allowed (the user has the link and confirmed rights).
        if availability == "needs_auth":
            return "This video isn't publicly available, so Snipzo can't import it."
    if age_limit >= 18:
        return "This video is age-restricted and can't be imported."
    if is_live or live_status in {"is_live", "is_upcoming"}:
        if live_status == "is_upcoming":
            return "This livestream hasn't started yet. Import it after it ends."
        return "This livestream is still in progress. Import it after it ends."
    return None


def friendly_from_message(message: str) -> str:
    """Map a yt-dlp error string to a user-facing sentence."""
    lower = message.lower()
    if "private video" in lower or "this video is private" in lower:
        return "This video is private, so Snipzo can't import it."
    if (
        "members-only" in lower
        or "members only" in lower
        or "join this channel" in lower
    ):
        return "This video is members-only, so Snipzo can't import it."
    if (
        "sign in to confirm your age" in lower
        or "age-restricted" in lower
        or "age restricted" in lower
    ):
        return "This video is age-restricted and can't be imported."
    if "live event will begin" in lower or "premiere will begin" in lower:
        return "This livestream hasn't started yet. Import it after it ends."
    if "this live event is over" in lower or "livestream is still in progress" in lower:
        return "This livestream is still in progress. Import it after it ends."
    if "this live event has ended" in lower:
        return (
            "This livestream has ended but the replay isn't available yet. "
            "Try again later."
        )
    if "playlist" in lower and "video" not in lower:
        return "Paste a link to a single video, not a playlist."
    if (
        "confirm you’re not a bot" in lower
        or "confirm you're not a bot" in lower
        or "sign in to confirm you’re not a bot" in lower
        or "sign in to confirm you're not a bot" in lower
        or "http error 429" in lower
        or "too many requests" in lower
    ):
        return (
            "YouTube blocked the download from this server. "
            "Try again later, or upload the file."
        )
    if "video unavailable" in lower or "this video is unavailable" in lower:
        return "This YouTube video is unavailable."
    if "http error 404" in lower or "not found" in lower:
        return "This YouTube video could not be found."
    return GENERIC_DOWNLOAD_ERROR


def info_from_extract(data: dict[str, Any], requested_url: str) -> YoutubeVideoInfo:
    """Build ``YoutubeVideoInfo`` from a yt-dlp extract_info dict, or raise."""
    if data.get("entries") and str(data.get("_type") or "") == "playlist":
        entries = [item for item in data["entries"] if item]
        if len(entries) == 1:
            data = entries[0]
        else:
            raise YoutubeUnavailable("Paste a link to a single video, not a playlist.")
    reason = friendly_restriction(data)
    if reason:
        raise YoutubeUnavailable(reason)
    video_id = str(data.get("id") or "")
    if not video_id:
        video_id = parse_youtube_video_id(requested_url)
    title = str(data.get("title") or "YouTube video").strip() or "YouTube video"
    duration_raw = data.get("duration")
    duration: float | None
    try:
        duration = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None
    if duration is not None and duration <= 0:
        duration = None
    thumbnail = data.get("thumbnail")
    thumbs = data.get("thumbnails")
    if not thumbnail and isinstance(thumbs, list) and thumbs:
        last = data["thumbnails"][-1] or {}
        thumbnail = last.get("url")
    thumb = str(thumbnail) if thumbnail else default_thumbnail_url(video_id)
    return YoutubeVideoInfo(
        video_id=video_id,
        title=title[:300],
        duration=duration,
        thumbnail_url=thumb,
        url=canonical_watch_url(video_id) if video_id else requested_url,
    )


def _base_opts(settings: ApiSettings) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
    }
    if settings.youtube_cookies_file:
        opts["cookiefile"] = str(settings.youtube_cookies_file)
    if settings.youtube_proxy:
        opts["proxy"] = settings.youtube_proxy
    return opts


class YtDlpDownloader:
    """Real yt-dlp backend. Never used in CI tests (the factory is replaced)."""

    def __init__(self, settings: ApiSettings | None = None) -> None:
        self.settings = settings or get_api_settings()

    def _ydl(self, extra: dict[str, Any]) -> Any:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover - dependency is in api extra
            raise SnipzoError(
                "yt-dlp is not installed. Install the api or pipeline extra."
            ) from exc
        opts = _base_opts(self.settings)
        opts.update(extra)
        return yt_dlp.YoutubeDL(opts)

    def probe(self, url: str) -> YoutubeVideoInfo:
        try:
            with self._ydl({"skip_download": True}) as ydl:
                data = ydl.extract_info(url, download=False)
        except Exception as exc:
            raw = str(exc)
            log.exception("yt-dlp probe failed for %s: %s", url, raw)
            raise YoutubeUnavailable(friendly_from_message(raw)) from exc
        if not isinstance(data, dict):
            raise YoutubeUnavailable("This YouTube video is unavailable.")
        return info_from_extract(data, url)

    def download(
        self, url: str, dest: Path, *, max_bytes: int, timeout: int
    ) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        outtmpl = str(dest.parent / f"{dest.stem}.%(ext)s")

        def hook(status: dict[str, Any]) -> None:
            if time.monotonic() - started > timeout:
                raise YoutubeUnavailable(
                    "Downloading this YouTube video took too long. "
                    "Try again, or upload the file."
                )
            downloaded = status.get("downloaded_bytes") or 0
            if max_bytes and downloaded > max_bytes:
                raise YoutubeUnavailable(
                    "This YouTube video is larger than the upload limit."
                )

        extra: dict[str, Any] = {
            "format": YOUTUBE_FORMAT,
            "merge_output_format": "mp4",
            "outtmpl": outtmpl,
            "progress_hooks": [hook],
        }
        if max_bytes:
            extra["max_filesize"] = max_bytes
        try:
            with self._ydl(extra) as ydl:
                ydl.download([url])
        except YoutubeUnavailable:
            raise
        except Exception as exc:
            raw = str(exc)
            log.exception("yt-dlp download failed for %s: %s", url, raw)
            lower = raw.lower()
            if "file is larger than max-filesize" in lower or "larger than" in lower:
                raise YoutubeUnavailable(
                    "This YouTube video is larger than the upload limit."
                ) from exc
            raise YoutubeUnavailable(friendly_from_message(raw)) from exc

        if dest.is_file() and dest.stat().st_size > 0:
            if max_bytes and dest.stat().st_size > max_bytes:
                dest.unlink(missing_ok=True)
                raise YoutubeUnavailable(
                    "This YouTube video is larger than the upload limit."
                )
            return dest
        candidates = sorted(
            dest.parent.glob(dest.stem + ".*"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            if candidate.suffix.lower() in {".mp4", ".mkv", ".webm", ".m4a"}:
                if max_bytes and candidate.stat().st_size > max_bytes:
                    candidate.unlink(missing_ok=True)
                    raise YoutubeUnavailable(
                        "This YouTube video is larger than the upload limit."
                    )
                if candidate != dest:
                    candidate.replace(dest)
                if dest.is_file() and dest.stat().st_size > 0:
                    return dest
        log.error("yt-dlp finished but produced no file for %s in %s", url, dest.parent)
        raise YoutubeUnavailable(GENERIC_DOWNLOAD_ERROR)


def default_downloader() -> YoutubeDownloader:
    return YtDlpDownloader(get_api_settings())


downloader_factory: Callable[[], YoutubeDownloader] = default_downloader


def get_downloader() -> YoutubeDownloader:
    return downloader_factory()


def probe_youtube(url: str) -> YoutubeVideoInfo:
    return get_downloader().probe(url)


def download_youtube(
    url: str, dest: Path, *, max_bytes: int, timeout: int
) -> Path:
    return get_downloader().download(
        url, dest, max_bytes=max_bytes, timeout=timeout
    )


def reject_oversize(
    info: YoutubeVideoInfo, raw: dict[str, Any] | None, max_bytes: int
) -> None:
    """Raise if metadata already says the file is over the upload cap."""
    if raw is None or max_bytes <= 0:
        return
    for key in ("filesize", "filesize_approx"):
        try:
            size = int(raw.get(key) or 0)
        except (TypeError, ValueError):
            size = 0
        if size > max_bytes:
            raise YoutubeUnavailable(
                "This YouTube video is larger than the upload limit."
            )
