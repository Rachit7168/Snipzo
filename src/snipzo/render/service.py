"""Render vertical Shorts with captions, a hook title, and loudness normalization."""

from __future__ import annotations

from pathlib import Path

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.media import probe_video, run_ffmpeg
from snipzo.models import (
    Clip,
    CropKeyframe,
    CropPath,
    Project,
    ProjectStatus,
    Render,
    Transcript,
)
from snipzo.pick.service import load_clips
from snipzo.projects import get_storage, resolve_project
from snipzo.reframe.geometry import center_origin, crop_size
from snipzo.reframe.service import load_crop_path
from snipzo.render.ass import build_ass, hook_title_from_words, words_for_clip
from snipzo.render.filters import (
    build_filter_complex,
    is_static_crop,
    write_sendcmd,
)
from snipzo.render.styles import (
    OUTPUT_FPS,
    OUTPUT_HEIGHT,
    OUTPUT_WIDTH,
    CaptionStyle,
    get_style,
)
from snipzo.storage import Storage
from snipzo.transcribe.service import load_transcript


def render_project(
    ref: str,
    settings: Settings,
    *,
    storage: Storage | None = None,
    style_id: str | None = None,
) -> tuple[Project, list[Render]]:
    """Render every clip in a project to a 1080x1920 H.264 Short."""
    store = storage or get_storage(settings.work_dir)
    project = resolve_project(ref, store)
    if not project.source_path.is_file():
        raise SnipzoError(f"Source video missing for project {project.id}.")
    clipset = load_clips(project)
    if not clipset.clips:
        raise SnipzoError(f"Project {project.id} has no clips to render.")
    transcript = load_transcript(project)
    style = get_style(style_id or settings.caption_style)
    renders_dir = store.project_root(project.id) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)

    renders: list[Render] = []
    for clip in clipset.clips:
        crop = _crop_or_center(project, clip)
        render = render_clip(
            project,
            clip,
            transcript,
            crop,
            style=style,
            dest=renders_dir / f"{clip.id}.mp4",
        )
        renders.append(render)

    store.write_json(
        project.id,
        "renders.json",
        {"renders": [item.model_dump(mode="json") for item in renders]},
    )
    updated = project.touch_status(ProjectStatus.RENDERED)
    store.save_project(updated)
    return updated, renders


def render_clip(
    project: Project,
    clip: Clip,
    transcript: Transcript,
    crop: CropPath,
    *,
    style: CaptionStyle,
    dest: Path,
) -> Render:
    """Render a single clip to `dest` with burned-in captions and audio polish."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    words = words_for_clip(transcript, clip)
    hook = hook_title_from_words(clip, words)
    ass_path = dest.with_suffix(".ass")
    ass_path.write_text(
        build_ass(words=words, clip=clip, style=style, hook_title=hook),
        encoding="utf-8",
    )
    sendcmd_path: Path | None = None
    if crop.mode != "blur" and not is_static_crop(crop):
        sendcmd_path = dest.with_suffix(".cmd")
        write_sendcmd(crop, sendcmd_path, clip.start)

    filters = build_filter_complex(
        clip=clip,
        crop=crop,
        style=style,
        ass_path=ass_path,
        sendcmd_path=sendcmd_path,
    )
    duration = max(clip.duration, 0.04)
    try:
        run_ffmpeg(
            [
                "-ss",
                f"{clip.start:.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(project.source_path),
                "-filter_complex",
                filters,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(OUTPUT_FPS),
                "-g",
                "60",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ac",
                "2",
                "-ar",
                "44100",
                "-movflags",
                "+faststart",
                "-t",
                f"{duration:.3f}",
                str(dest),
            ]
        )
    except SnipzoError:
        raise
    if not dest.is_file() or dest.stat().st_size == 0:
        raise SnipzoError(f"Failed to render {clip.id} for project {project.id}.")

    info = probe_video(dest)
    if info.width != OUTPUT_WIDTH or info.height != OUTPUT_HEIGHT:
        raise SnipzoError(
            f"Rendered {clip.id} is {info.width}x{info.height}, "
            f"expected {OUTPUT_WIDTH}x{OUTPUT_HEIGHT}."
        )
    return Render(
        clip_id=clip.id,
        path=dest,
        width=info.width,
        height=info.height,
        fps=info.fps,
        duration=info.duration,
        style_id=style.id,
    )


def _crop_or_center(project: Project, clip: Clip) -> CropPath:
    try:
        return load_crop_path(project, clip.id)
    except SnipzoError:
        width = project.source.width
        height = project.source.height
        crop_w, crop_h = crop_size(width, height)
        x, y = center_origin(width, height, crop_w, crop_h)
        key = CropKeyframe(t=clip.start, x=x, y=y, w=crop_w, h=crop_h)
        end_key = CropKeyframe(t=clip.end, x=x, y=y, w=crop_w, h=crop_h)
        return CropPath(
            clip_id=clip.id,
            mode="center",
            source_width=width,
            source_height=height,
            keyframes=[key, end_key],
        )
