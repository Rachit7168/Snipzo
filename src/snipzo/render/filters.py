"""Build the FFmpeg filter graph for a vertical Short."""

from __future__ import annotations

from pathlib import Path

from snipzo.models import Clip, CropPath
from snipzo.render.styles import OUTPUT_HEIGHT, OUTPUT_WIDTH, CaptionStyle


def is_static_crop(path: CropPath, threshold: float = 12.0) -> bool:
    """True when the crop window barely moves."""
    if len(path.keyframes) <= 1:
        return True
    xs = [key.x for key in path.keyframes]
    ys = [key.y for key in path.keyframes]
    return (max(xs) - min(xs) < threshold) and (max(ys) - min(ys) < threshold)


def escape_filter_path(path: Path) -> str:
    """Escape a file path for an FFmpeg filter argument."""
    text = path.resolve().as_posix().replace("\\", "/").replace("'", r"\'")
    text = text.replace(":", r"\:")
    return f"'{text}'"


def write_sendcmd(path: CropPath, dest: Path, clip_start: float) -> Path:
    """Write an FFmpeg sendcmd file with crop x/y updates (clip-relative times)."""
    lines: list[str] = []
    first = path.keyframes[0]
    lines.append(
        f"{0.0:.3f} crop w {int(first.w)}, crop h {int(first.h)}, "
        f"crop x {first.x:.2f}, crop y {first.y:.2f};"
    )
    last_x, last_y = first.x, first.y
    for key in path.keyframes[1:]:
        time = max(0.0, key.t - clip_start)
        parts: list[str] = []
        if abs(key.x - last_x) >= 0.5:
            parts.append(f"crop x {key.x:.2f}")
            last_x = key.x
        if abs(key.y - last_y) >= 0.5:
            parts.append(f"crop y {key.y:.2f}")
            last_y = key.y
        if parts:
            lines.append(f"{time:.3f} " + ", ".join(parts) + ";")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def build_filter_complex(
    *,
    clip: Clip,
    crop: CropPath,
    style: CaptionStyle,
    ass_path: Path,
    sendcmd_path: Path | None,
) -> str:
    """Return the FFmpeg `-filter_complex` graph for one clip."""
    duration = max(clip.duration, 0.04)
    bar = (
        f"drawbox=x=0:y=ih-14:w='iw*min(1\\,t/{duration:.3f})':h=14:"
        f"color={style.progress_color}:t=fill"
    )
    subs = f"subtitles={escape_filter_path(ass_path)}"
    video = _video_filters(crop, sendcmd_path)
    audio = "loudnorm=I=-14:LRA=11:TP=-1.5"
    return f"[0:v]{video},{subs},{bar}[vout];[0:a]{audio}[aout]"


def _video_filters(crop: CropPath, sendcmd_path: Path | None) -> str:
    scale = f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:flags=lanczos"
    if crop.mode == "blur":
        return (
            f"split=2[bg][fg];"
            f"[bg]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},boxblur=20:8[bgblur];"
            f"[fg]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=decrease"
            f"[fgfit];"
            f"[bgblur][fgfit]overlay=(W-w)/2:(H-h)/2"
        )
    first = crop.keyframes[0]
    w, h, x, y = int(first.w), int(first.h), first.x, first.y
    if sendcmd_path is not None and not is_static_crop(crop):
        cmd = escape_filter_path(sendcmd_path)
        return f"sendcmd=f={cmd},crop={w}:{h}:{x:.2f}:{y:.2f},{scale}"
    return f"crop={w}:{h}:{x:.2f}:{y:.2f},{scale}"
