"""User-facing error sanitization for background jobs and API responses."""

from __future__ import annotations

import re

from snipzo.api.youtube import YouTubeError
from snipzo.api.ytdlp import YoutubeUnavailable

_ENV_VAR_RE = re.compile(r"\bSNIPZO_[A-Z0-9_]+\b")
_PATH_RE = re.compile(r"(?:/tmp/|/var/|/home/|/workspace/|/app/)[^\s,;\"']+")
_PROJECT_ID_RE = re.compile(r"\bfor project [a-f0-9]{8,}\b", re.IGNORECASE)

GENERIC_JOB_ERROR = (
    "Processing failed unexpectedly. Try another file or contact support."
)
UNREADABLE_VIDEO_ERROR = (
    "We couldn't read this video file. Please upload a valid MP4, MOV, WebM, "
    "or MKV file."
)
NO_AUDIO_ERROR = (
    "This video has no audio track. Snipzo needs spoken audio to create Shorts."
)
NO_SPEECH_ERROR = (
    "We couldn't find enough spoken dialogue in this video to create Shorts. "
    "Try a video with clearer speech."
)
RENDER_ERROR = (
    "Rendering one of the clips failed. Try again or upload a different video."
)
PUBLISH_ERROR = (
    "Publishing to YouTube failed. Check your channel connection and try again."
)


def scrub_internals(text: str) -> str:
    """Strip filesystem paths, env-var names, and internal IDs from a message."""
    cleaned = _ENV_VAR_RE.sub("server configuration", text)
    cleaned = _PATH_RE.sub("the uploaded file", cleaned)
    cleaned = _PROJECT_ID_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def sanitize_job_error(exc: Exception) -> str:
    """Map an arbitrary pipeline/job exception to a short, safe user message."""
    if isinstance(exc, YoutubeUnavailable):
        return scrub_internals(str(exc)) or GENERIC_JOB_ERROR

    raw = str(exc) or type(exc).__name__
    lower = raw.lower()

    if "plan has" in lower or "plan includes" in lower or "upgrade or use" in lower:
        return scrub_internals(raw)

    if "deleted after the retention window" in lower:
        return "The source video was deleted after the retention window."

    if "turned off on this server" in lower:
        return (
            "YouTube import is not available on this server. "
            "Upload the video file instead."
        )

    if "no audio stream" in lower:
        return NO_AUDIO_ERROR

    if (
        "ffprobe" in lower
        or "moov atom" in lower
        or "invalid data found" in lower
        or "no video stream" in lower
        or "could not determine duration" in lower
        or "could not determine resolution" in lower
        or "could not determine frame rate" in lower
        or "not a video" in lower
    ):
        return UNREADABLE_VIDEO_ERROR

    if (
        "transcription produced no text" in lower
        or "no speech" in lower
        or "empty transcript" in lower
    ):
        return NO_SPEECH_ERROR

    if (
        "ffmpeg" in lower
        or "render" in lower
        or "reframe" in lower
        or "subtitle" in lower
        or "clip" in lower
    ):
        return RENDER_ERROR

    if (
        "source video is larger" in lower
        or "downloaded file is empty" in lower
        or "download failed with http" in lower
    ):
        return scrub_internals(raw)

    return GENERIC_JOB_ERROR


def sanitize_publish_error(exc: Exception) -> str:
    """Map a YouTube publishing exception to a safe user-facing message."""
    raw = str(exc) or type(exc).__name__
    lower = raw.lower()
    if "reconnect youtube" in lower or "connection expired" in lower:
        return (
            "Your YouTube channel connection expired. "
            "Reconnect it on the Channels page."
        )
    if "no rendered video" in lower:
        return "This clip doesn't have a rendered video yet."
    if "no longer exists" in lower or "not found" in lower:
        return "The selected channel or clip is no longer available."
    if isinstance(exc, YouTubeError):
        if "401" in lower or "403" in lower or "token" in lower:
            return (
                "YouTube rejected the upload credentials. "
                "Reconnect your channel and try again."
            )
        return PUBLISH_ERROR
    return PUBLISH_ERROR
