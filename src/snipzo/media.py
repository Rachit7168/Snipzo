"""FFmpeg and ffprobe helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from snipzo.errors import SnipzoError
from snipzo.models import VideoInfo


def ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise SnipzoError("ffmpeg is not installed or not on PATH.")
    return path


def ffprobe_bin() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise SnipzoError("ffprobe is not installed or not on PATH.")
    return path


def run_ffmpeg(args: list[str], *, timeout: float | None = None) -> None:
    """Run ffmpeg, raising SnipzoError on failure."""
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", *args]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise SnipzoError("ffmpeg is not installed or not on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise SnipzoError(f"ffmpeg timed out after {timeout}s.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SnipzoError(f"ffmpeg failed: {detail or 'unknown error'}")


def probe_video(path: Path) -> VideoInfo:
    """Validate a local video and return duration, resolution, fps, and audio info."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SnipzoError(f"Video not found: {path}")

    cmd = [
        ffprobe_bin(),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(resolved),
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SnipzoError("ffprobe is not installed or not on PATH.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SnipzoError(f"ffprobe could not read {path}: {detail or 'invalid file'}")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SnipzoError(f"ffprobe returned invalid JSON for {path}.") from exc

    streams = _dict_list(payload.get("streams"))
    format_info = _as_dict(payload.get("format"))
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise SnipzoError(f"No video stream found in {path}.")

    duration_sources = [format_info, video_stream]
    if audio_stream is not None:
        duration_sources.append(audio_stream)
    duration = _duration(*duration_sources)
    if duration <= 0:
        raise SnipzoError(f"Could not determine duration for {path}.")

    width = _as_int(video_stream.get("width"))
    height = _as_int(video_stream.get("height"))
    if width <= 0 or height <= 0:
        raise SnipzoError(f"Could not determine resolution for {path}.")

    fps = _fps(video_stream)
    if fps <= 0:
        raise SnipzoError(f"Could not determine frame rate for {path}.")

    if audio_stream is None:
        raise SnipzoError(
            f"No audio stream found in {path}; transcription needs audio."
        )

    codec_raw = video_stream.get("codec_name")
    codec = str(codec_raw) if codec_raw else None

    return VideoInfo(
        path=resolved,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio=True,
        codec=codec,
    )


def extract_wav(video: Path, dest: Path) -> Path:
    """Extract 16 kHz mono PCM audio for transcription."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )
    if not dest.is_file() or dest.stat().st_size == 0:
        raise SnipzoError(f"Failed to extract audio from {video}.")
    return dest


def _duration(*sources: dict[str, object]) -> float:
    for source in sources:
        value = _as_float(source.get("duration"))
        if value is not None and value > 0:
            return value
    return 0.0


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [_as_dict(item) for item in value if isinstance(item, dict)]


def _as_int(value: object) -> int:
    if value is None or value is False:
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _as_float(value: object) -> float | None:
    if value is None or value is False:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _fps(video_stream: dict[str, object]) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = video_stream.get(key)
        if not raw or raw == "0/0":
            continue
        text = str(raw)
        if "/" in text:
            num_s, den_s = text.split("/", 1)
            try:
                num, den = float(num_s), float(den_s)
            except ValueError:
                continue
            if den != 0:
                return num / den
        else:
            try:
                value = float(text)
            except ValueError:
                continue
            if value > 0:
                return value
    return 0.0
