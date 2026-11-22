"""Job logic shared by Celery tasks: fetch sources, run the pipeline, sync results."""

from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from snipzo.api.blobstore import BlobStore, get_blob_store, render_key, source_key
from snipzo.api.db import session_scope
from snipzo.api.settings import ApiSettings, get_api_settings
from snipzo.api.tables import ClipRow, Job, ProjectRow, RenderRow, TranscriptRow, User
from snipzo.config import Settings, get_settings
from snipzo.errors import SnipzoError
from snipzo.models import ClipMetadata, Render
from snipzo.pipeline import STAGES, run_pipeline
from snipzo.projects import get_storage, resolve_project
from snipzo.transcribe.base import Transcriber

log = logging.getLogger(__name__)

# TikTok/Instagram page links stay blocked; YouTube video URLs are handled by yt-dlp.

# Tests replace this to avoid loading Whisper models.
TranscriberFactory = Callable[[Settings], Transcriber | None]
transcriber_factory: TranscriberFactory = lambda settings: None  # noqa: E731


def pipeline_settings() -> Settings:
    """Settings for the pipeline scratch directory (shared by all workers)."""
    return get_settings()


def blob_store() -> BlobStore:
    return get_blob_store(get_api_settings())


def classify_source_url(url: str) -> tuple[str, str]:
    """Return ``("youtube", canonical)`` or ``("url", direct_file_url)``."""
    from snipzo.youtube_url import classify_source_url as _classify

    return _classify(url)


def validate_source_url(url: str) -> str:
    """Accept a YouTube video URL or a direct http(s) file link."""
    _kind, normalised = classify_source_url(url)
    return normalised


def download_url(url: str, dest: Path, *, max_bytes: int) -> Path:
    """Stream a direct video URL to `dest`, enforcing a size limit."""
    validate_source_url(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
        if response.status_code >= 400:
            raise SnipzoError(f"Download failed with HTTP {response.status_code}.")
        with dest.open("wb") as handle:
            for chunk in response.iter_bytes():
                written += len(chunk)
                if written > max_bytes:
                    raise SnipzoError("Source video is larger than the upload limit.")
                handle.write(chunk)
    if written == 0:
        raise SnipzoError("Downloaded file is empty.")
    return dest


def _update_job(
    job_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    message: str | None = None,
    error: str | None = None,
    project_status: str | None = None,
) -> None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        if status:
            job.status = status
        if stage:
            job.stage = stage
            if stage in STAGES:
                job.progress = round(STAGES.index(stage) / len(STAGES), 3)
        if message is not None:
            job.message = message[:2000]
        if error is not None:
            job.error = error[:4000]
        if status == "succeeded":
            job.progress = 1.0
        project = session.get(ProjectRow, job.project_id)
        if project is not None:
            if project_status:
                project.status = project_status
            if error is not None:
                project.error = error[:4000]


def _load_job(session: Session, job_id: str) -> tuple[Job, ProjectRow]:
    job = session.get(Job, job_id)
    if job is None:
        raise SnipzoError(f"Job not found: {job_id}")
    project = session.get(ProjectRow, job.project_id)
    if project is None:
        raise SnipzoError(f"Project not found for job {job_id}")
    return job, project


def run_ingest_and_transcribe(job_id: str) -> bool:
    """Stage 1 (GPU queue): fetch the source, ingest it, and transcribe.

    Failures are recorded on the job (and returned as False) rather than raised,
    so the follow-up render stage can skip cleanly.
    """
    from snipzo.ingest import ingest_video
    from snipzo.transcribe import transcribe_project

    api_settings = get_api_settings()
    settings = pipeline_settings()
    store = blob_store()
    with session_scope() as session:
        job, project = _load_job(session, job_id)
        project_id = project.id
        kind = project.source_kind
        url = project.source_url
        key = project.source_key
        filename = project.source_filename or "source.mp4"
        job.status = "running"

    try:
        _update_job(
            job_id,
            stage="ingest",
            message="Fetching source video...",
            project_status="ingesting",
        )
        scratch = Path(tempfile.mkdtemp(prefix="snipzo-src-"))
        try:
            local = scratch / Path(filename).name
            if kind == "youtube":
                from snipzo.api import billing as billing_mod
                from snipzo.api.ytdlp import download_youtube, probe_youtube

                if not url:
                    raise SnipzoError("Project has no YouTube video.")
                if api_settings.youtube_import_downloader == "disabled":
                    raise SnipzoError(
                        "YouTube import is turned off on this server. "
                        "Upload the file instead."
                    )
                info = probe_youtube(url)
                with session_scope() as session:
                    row = session.get(ProjectRow, project_id)
                    if row is not None:
                        row.source_title = row.source_title or info.title
                        row.source_thumbnail_url = (
                            row.source_thumbnail_url or info.thumbnail_url
                        )
                        if info.duration:
                            row.duration_seconds = info.duration
                        owner = session.get(User, row.user_id)
                        if owner is not None and info.duration:
                            billing_mod.check_minutes(
                                session,
                                owner,
                                api_settings,
                                info.duration / 60.0,
                            )
                local = local.with_suffix(".mp4")
                download_youtube(
                    url,
                    local,
                    max_bytes=api_settings.max_upload_mb * 2**20,
                    timeout=api_settings.youtube_download_timeout,
                )
                key = source_key(project_id, local.name)
                store.put_file(key, local)
                with session_scope() as session:
                    row = session.get(ProjectRow, project_id)
                    if row is not None:
                        row.source_key = key
            elif kind == "url":
                if not url:
                    raise SnipzoError("Project has no source URL.")
                download_url(url, local, max_bytes=api_settings.max_upload_mb * 2**20)
                key = source_key(project_id, local.name)
                store.put_file(key, local)
                with session_scope() as session:
                    row = session.get(ProjectRow, project_id)
                    if row is not None:
                        row.source_key = key
            else:
                if not key:
                    raise SnipzoError("Project has no uploaded source.")
                store.get_file(key, local)
            project_model = ingest_video(
                local,
                settings,
                storage=get_storage(settings.work_dir),
                project_id=project_id,
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

        from snipzo.api import billing

        with session_scope() as session:
            row = session.get(ProjectRow, project_id)
            if row is not None:
                row.duration_seconds = project_model.source.duration
                owner = session.get(User, row.user_id)
                minutes = project_model.source.duration / 60.0
                if owner is not None:
                    billing.check_minutes(session, owner, api_settings, minutes)
                    billing.record_usage(session, owner.id, project_id, minutes)

        _update_job(
            job_id,
            stage="transcribe",
            message="Transcribing audio...",
            project_status="transcribing",
        )
        _, transcript = transcribe_project(
            project_id, settings, transcriber=transcriber_factory(settings)
        )
        with session_scope() as session:
            existing = session.scalar(
                select(TranscriptRow).where(TranscriptRow.project_id == project_id)
            )
            row_t = existing or TranscriptRow(project_id=project_id)
            row_t.language = transcript.language
            row_t.word_count = len(transcript.words)
            row_t.text = transcript.text()
            row_t.backend = transcript.backend
            session.add(row_t)
        return True
    except Exception as exc:
        log.exception("ingest/transcribe failed for job %s", job_id)
        _update_job(
            job_id,
            status="failed",
            error=str(exc) or type(exc).__name__,
            project_status="failed",
        )
        return False


def run_highlights_and_render(job_id: str) -> bool:
    """Stage 2 (CPU queue): pick, metadata, reframe, render, then publish results."""
    settings = pipeline_settings()
    store = blob_store()
    with session_scope() as session:
        job, project = _load_job(session, job_id)
        project_id = project.id
        if job.status == "failed":
            return False

    def on_progress(stage: str, message: str) -> None:
        _update_job(job_id, stage=stage, message=message, project_status=stage)

    try:
        run_pipeline(None, settings, project_ref=project_id, on_progress=on_progress)
        sync_project_outputs(project_id, settings, store)
        _update_job(
            job_id,
            status="succeeded",
            stage="render",
            message="Shorts ready.",
            project_status="complete",
        )
        return True
    except Exception as exc:
        log.exception("pipeline failed for job %s", job_id)
        _update_job(
            job_id,
            status="failed",
            error=str(exc) or type(exc).__name__,
            project_status="failed",
        )
        return False


def run_rerender(job_id: str) -> bool:
    """Re-render one edited clip (CPU queue) and publish a new render version."""
    from snipzo.edit import rerender_clip

    settings = pipeline_settings()
    store = blob_store()
    with session_scope() as session:
        job, project = _load_job(session, job_id)
        project_id = project.id
        clip_id = str(job.payload.get("clip_id", ""))
        reframe = bool(job.payload.get("reframe", False))
        job.status = "running"
    try:
        _update_job(job_id, stage="render", message=f"Re-rendering {clip_id}...")
        local = get_storage(settings.work_dir)
        project_model = resolve_project(project_id, local)
        if not project_model.source_path.is_file():
            with session_scope() as session:
                row = session.get(ProjectRow, project_id)
                key = row.source_key if row and row.source_deleted_at is None else None
            if not key:
                raise SnipzoError(
                    "The source video was deleted after the retention window."
                )
            store.get_file(key, project_model.source_path)
        rerender_clip(project_id, clip_id, settings, reframe=reframe)
        sync_project_outputs(project_id, settings, store, clip_ids={clip_id})
        _update_job(job_id, status="succeeded", message=f"{clip_id} re-rendered.")
        return True
    except Exception as exc:
        log.exception("re-render failed for job %s", job_id)
        _update_job(job_id, status="failed", error=str(exc) or type(exc).__name__)
        return False


def sync_project_outputs(
    project_id: str,
    settings: Settings,
    store: BlobStore,
    *,
    clip_ids: set[str] | None = None,
) -> None:
    """Upload rendered MP4s and mirror clips/metadata/renders into the database."""
    from snipzo.pick.service import load_clips

    local_store = get_storage(settings.work_dir)
    project = resolve_project(project_id, local_store)
    clipset = load_clips(project)
    renders: dict[str, Render] = {}
    if (project.root / "renders.json").is_file():
        payload = local_store.read_json(project_id, "renders.json")
        if isinstance(payload, dict):
            for item in payload.get("renders", []):
                render = Render.model_validate(item)
                renders[render.clip_id] = render

    from snipzo.api import billing

    api_settings = get_api_settings()
    with session_scope() as session:
        project_row = session.get(ProjectRow, project_id)
        owner = session.get(User, project_row.user_id) if project_row else None
        plan = (
            billing.plan_for(owner, api_settings)
            if owner
            else billing.plans(api_settings)["free"]
        )
        for rank, clip in enumerate(clipset.clips, start=1):
            if clip_ids is not None and clip.id not in clip_ids:
                continue
            row = session.scalar(
                select(ClipRow).where(
                    ClipRow.project_id == project_id, ClipRow.clip_id == clip.id
                )
            )
            if row is None:
                row = ClipRow(project_id=project_id, clip_id=clip.id)
                session.add(row)
            row.rank = rank
            row.start = clip.start
            row.end = clip.end
            row.score = clip.score
            row.reason = clip.reason
            row.hook_title = clip.hook_title
            meta_path = project.renders_dir / f"{clip.id}.json"
            if meta_path.is_file():
                meta = ClipMetadata.model_validate_json(
                    meta_path.read_text(encoding="utf-8")
                )
                row.title = meta.title
                row.description = meta.description
                row.hashtags = list(meta.hashtags)
            mp4 = project.renders_dir / f"{clip.id}.mp4"
            if not mp4.is_file():
                continue
            session.flush()
            billing.apply_plan_to_render(mp4, plan)
            info = renders.get(clip.id)
            out_height = min(info.height if info else 1920, plan.max_height)
            out_width = int(round(out_height * 9 / 16 / 2) * 2)
            version = len(row.renders) + 1
            key = render_key(project_id, clip.id, version)
            store.put_file(key, mp4, content_type="video/mp4")
            if info is not None:
                row.style_id = info.style_id
            session.add(
                RenderRow(
                    clip_row_id=row.id,
                    blob_key=key,
                    width=out_width,
                    height=out_height,
                    duration=info.duration if info else clip.duration,
                    size_bytes=mp4.stat().st_size,
                    version=version,
                )
            )


def cleanup_sources(
    retention_days: int | None = None, *, now: datetime | None = None
) -> list[str]:
    """Delete source videos older than the retention window; return project ids."""
    api_settings: ApiSettings = get_api_settings()
    days = retention_days or api_settings.source_retention_days
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    store = blob_store()
    work_dir = pipeline_settings().work_dir
    cleaned: list[str] = []
    with session_scope() as session:
        rows = session.scalars(
            select(ProjectRow).where(ProjectRow.source_deleted_at.is_(None))
        ).all()
        for row in rows:
            created = row.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if created >= cutoff:
                continue
            if row.source_key:
                store.delete(row.source_key)
            project_dir = Path(work_dir) / row.id
            for item in project_dir.glob("source.*"):
                item.unlink(missing_ok=True)
            row.source_deleted_at = datetime.now(UTC)
            cleaned.append(row.id)
    return cleaned
