"""End-to-end pipeline: ingest through render, with resumable stages."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.ingest import ingest_video
from snipzo.metadata import generate_metadata
from snipzo.models import Project, ProjectStatus
from snipzo.pick import pick_clips
from snipzo.projects import get_storage, resolve_project
from snipzo.reframe import reframe_project
from snipzo.render import render_project
from snipzo.storage import Storage
from snipzo.transcribe import transcribe_project
from snipzo.transcribe.base import Transcriber

Stage = Literal["ingest", "transcribe", "pick", "metadata", "reframe", "render"]
STAGES: tuple[Stage, ...] = (
    "ingest",
    "transcribe",
    "pick",
    "metadata",
    "reframe",
    "render",
)
ProgressFn = Callable[[Stage, str], None]


def run_pipeline(
    video: Path | None,
    settings: Settings,
    *,
    project_ref: str | None = None,
    force: bool = False,
    top_n: int | None = None,
    style_id: str | None = None,
    storage: Storage | None = None,
    transcriber: Transcriber | None = None,
    on_progress: ProgressFn | None = None,
) -> Project:
    """Run or resume the pipeline.

    Metadata runs before render so hook titles are burned into the Shorts.
    """
    store = storage or get_storage(settings.work_dir)
    project = _initial_project(
        video, settings, project_ref=project_ref, force=force, storage=store
    )
    _emit(on_progress, "ingest", f"Project {project.id} at {project.root}")

    if force or not _done(project, "transcribe"):
        _emit(on_progress, "transcribe", "Transcribing audio...")
        project, transcript = transcribe_project(
            project.id, settings, storage=store, transcriber=transcriber
        )
        _emit(
            on_progress,
            "transcribe",
            f"{transcript.language}, {len(transcript.words)} words",
        )
    else:
        _emit(on_progress, "transcribe", "Skipping (transcript.json exists)")

    if force or not _done(project, "pick"):
        _emit(on_progress, "pick", "Selecting highlight clips...")
        project, clipset = pick_clips(
            project.id, settings, storage=store, top_n=top_n
        )
        _emit(on_progress, "pick", f"{len(clipset.clips)} clips ({clipset.scorer})")
    else:
        _emit(on_progress, "pick", "Skipping (clips.json exists)")

    # Metadata first so hook titles are available to the renderer.
    if force or not _done(project, "metadata"):
        _emit(on_progress, "metadata", "Generating titles and hashtags...")
        _, items = generate_metadata(project.id, settings, storage=store)
        _emit(on_progress, "metadata", f"{len(items)} metadata files")
    else:
        _emit(on_progress, "metadata", "Skipping (metadata.json exists)")

    if force or not _done(project, "reframe"):
        _emit(on_progress, "reframe", "Computing 9:16 crop paths...")
        project, paths = reframe_project(project.id, settings, storage=store)
        _emit(on_progress, "reframe", f"{len(paths)} crop paths")
    else:
        _emit(on_progress, "reframe", "Skipping (crops.json exists)")

    if force or not _done(project, "render"):
        _emit(on_progress, "render", "Rendering Shorts...")
        project, renders = render_project(
            project.id, settings, storage=store, style_id=style_id
        )
        _emit(on_progress, "render", f"{len(renders)} files in {project.renders_dir}")
    else:
        _emit(on_progress, "render", "Skipping (renders already exist)")

    project = project.touch_status(ProjectStatus.COMPLETE)
    store.save_project(project)
    return project


def _initial_project(
    video: Path | None,
    settings: Settings,
    *,
    project_ref: str | None,
    force: bool,
    storage: Storage,
) -> Project:
    if project_ref:
        project = resolve_project(project_ref, storage)
        if force or not _done(project, "ingest"):
            if video is None:
                raise SnipzoError(
                    f"Project {project.id} is missing ingest artifacts; "
                    "pass a video path."
                )
            project = ingest_video(
                video, settings, storage=storage, project_id=project.id
            )
        return project
    if video is None:
        raise SnipzoError(
            "Provide a video path, or --project to resume an existing run."
        )
    return ingest_video(video, settings, storage=storage)


def _done(project: Project, stage: Stage) -> bool:
    if stage == "ingest":
        return project.project_json_path.is_file() and project.audio_path.is_file()
    if stage == "transcribe":
        return project.transcript_path.is_file()
    if stage == "pick":
        return project.clips_path.is_file()
    if stage == "metadata":
        return (project.root / "metadata.json").is_file()
    if stage == "reframe":
        return (project.root / "crops.json").is_file()
    if stage == "render":
        if not project.clips_path.is_file():
            return False
        from snipzo.pick.service import load_clips

        clips = load_clips(project)
        if not clips.clips:
            return False
        return all(
            (project.renders_dir / f"{clip.id}.mp4").is_file() for clip in clips.clips
        )
    return False


def _emit(on_progress: ProgressFn | None, stage: Stage, message: str) -> None:
    if on_progress is not None:
        on_progress(stage, message)
