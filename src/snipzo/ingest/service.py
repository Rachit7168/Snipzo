"""Create a project from a local video file."""

from __future__ import annotations

import uuid
from pathlib import Path

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.media import extract_wav, probe_video
from snipzo.models import Project, ProjectStatus, VideoInfo
from snipzo.storage import LocalStorage, Storage


def new_project_id() -> str:
    """Return a short unique project identifier."""
    return uuid.uuid4().hex[:12]


def ingest_video(
    video: Path,
    settings: Settings,
    *,
    storage: Storage | None = None,
    project_id: str | None = None,
) -> Project:
    """Validate `video`, copy it into a new project, and extract 16 kHz mono audio."""
    resolved = video.expanduser().resolve()
    if not resolved.is_file():
        raise SnipzoError(f"Video not found: {video}")

    info = probe_video(resolved)
    store = storage or LocalStorage(settings.work_dir)
    pid = project_id or new_project_id()
    dest_name = f"source{resolved.suffix.lower() or '.mp4'}"
    stored = store.copy_into(pid, resolved, dest_name)
    audio = store.project_root(pid) / "audio.wav"
    extract_wav(stored, audio)

    source = VideoInfo(
        path=stored,
        duration=info.duration,
        width=info.width,
        height=info.height,
        fps=info.fps,
        has_audio=info.has_audio,
        codec=info.codec,
    )
    project = Project(
        id=pid,
        status=ProjectStatus.INGESTED,
        source=source,
        work_dir=Path(store.project_root(pid).parent),
    )
    store.save_project(project)
    return project
