"""FastAPI application: auth, uploads, job status, clips, and downloads."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import func, select

from snipzo import __version__
from snipzo.api import jobs
from snipzo.api.blobstore import get_blob_store, source_key
from snipzo.api.deps import Config, CurrentUser, DbSession
from snipzo.api.schemas import (
    ClipOut,
    Credentials,
    JobOut,
    ProjectOut,
    TokenOut,
    UserOut,
)
from snipzo.api.security import hash_password, sign, unsign, verify_password
from snipzo.api.settings import ApiSettings, get_api_settings
from snipzo.api.tables import ClipRow, Job, ProjectRow, User
from snipzo.errors import SnipzoError
from snipzo.ingest.service import new_project_id

ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name, plan=user.plan)


def issue_token(user: User, settings: ApiSettings) -> TokenOut:
    token = sign(
        {"sub": user.id, "typ": "access"},
        settings.secret_key,
        settings.token_ttl_seconds,
    )
    return TokenOut(access_token=token, user=user_out(user))


def download_link(blob_key: str, settings: ApiSettings) -> str:
    token = sign(
        {"k": blob_key, "typ": "dl"}, settings.secret_key, settings.download_ttl_seconds
    )
    return f"{settings.public_api_url.rstrip('/')}/files/{token}"


def job_out(job: Job | None) -> JobOut | None:
    if job is None:
        return None
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def clip_out(row: ClipRow, settings: ApiSettings) -> ClipOut:
    latest = max(row.renders, key=lambda item: item.version) if row.renders else None
    return ClipOut(
        clip_id=row.clip_id,
        rank=row.rank,
        start=row.start,
        end=row.end,
        duration=max(0.0, row.end - row.start),
        score=row.score,
        reason=row.reason,
        hook_title=row.hook_title,
        title=row.title,
        description=row.description,
        hashtags=list(row.hashtags or []),
        style_id=row.style_id,
        render_version=latest.version if latest else None,
        download_url=download_link(latest.blob_key, settings) if latest else None,
    )


def project_out(row: ProjectRow, settings: ApiSettings, *, clips: bool) -> ProjectOut:
    return ProjectOut(
        id=row.id,
        title=row.title,
        status=row.status,
        source_kind=row.source_kind,
        source_filename=row.source_filename,
        duration_seconds=row.duration_seconds,
        rights_confirmed=row.rights_confirmed,
        source_available=row.source_deleted_at is None,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        job=job_out(row.jobs[-1] if row.jobs else None),
        clips=[clip_out(item, settings) for item in row.clips] if clips else [],
    )


def owned_project(db: DbSession, user: User, project_id: str) -> ProjectRow:
    row = db.get(ProjectRow, project_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return row


def enqueue(job_id: str) -> None:
    """Hand a pipeline job to Celery (patched in tests if needed)."""
    from snipzo.api.worker import enqueue_pipeline

    enqueue_pipeline(job_id)


auth = APIRouter(prefix="/auth", tags=["auth"])


@auth.post("/register", response_model=TokenOut, status_code=201)
def register(body: Credentials, db: DbSession, settings: Config) -> TokenOut:
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid email.")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered.")
    user = User(email=email, password_hash=hash_password(body.password), name=body.name)
    db.add(user)
    db.flush()
    return issue_token(user, settings)


@auth.post("/login", response_model=TokenOut)
def login(body: Credentials, db: DbSession, settings: Config) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.")
    return issue_token(user, settings)


@auth.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user_out(user)


projects = APIRouter(prefix="/projects", tags=["projects"])


@projects.post("", response_model=ProjectOut, status_code=201)
def create_project(
    db: DbSession,
    user: CurrentUser,
    settings: Config,
    rights_confirmed: Annotated[bool, Form()] = False,
    title: Annotated[str | None, Form()] = None,
    source_url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> ProjectOut:
    """Upload a video (or give a direct file URL) and start processing."""
    if not rights_confirmed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Confirm that you own or have rights to this content.",
        )
    has_file = file is not None and bool(file.filename)
    if has_file == bool(source_url):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Provide exactly one of file or source_url."
        )
    project_id = new_project_id()
    row = ProjectRow(
        id=project_id,
        user_id=user.id,
        title=title,
        rights_confirmed=True,
        status="queued",
    )
    if file is not None and has_file:
        filename = Path(file.filename or "upload.mp4").name
        if Path(filename).suffix.lower() not in ALLOWED_SUFFIXES:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported video type."
            )
        key = source_key(project_id, filename)
        _store_upload(file, key, settings)
        row.source_kind = "upload"
        row.source_key = key
        row.source_filename = filename
    else:
        if not settings.url_import_enabled:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "URL import is disabled.")
        try:
            url = jobs.validate_source_url(source_url or "")
        except SnipzoError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        row.source_kind = "url"
        row.source_url = url
        row.source_filename = Path(url.split("?", 1)[0]).name or "source.mp4"
    row.title = row.title or Path(row.source_filename or "video").stem
    db.add(row)
    job = Job(project_id=project_id, kind="pipeline", status="queued")
    db.add(job)
    db.commit()
    enqueue(job.id)
    db.expire_all()
    fresh = owned_project(db, user, project_id)
    return project_out(fresh, settings, clips=True)


def _store_upload(file: UploadFile, key: str, settings: ApiSettings) -> None:
    limit = settings.max_upload_mb * 2**20
    tmp_dir = Path(tempfile.mkdtemp(prefix="snipzo-up-"))
    try:
        tmp = tmp_dir / "upload"
        written = 0
        with tmp.open("wb") as handle:
            while chunk := file.file.read(2**20):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE, "Upload too large."
                    )
                handle.write(chunk)
        if written == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty.")
        get_blob_store(settings).put_file(key, tmp, content_type=file.content_type)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@projects.get("", response_model=list[ProjectOut])
def list_projects(
    db: DbSession, user: CurrentUser, settings: Config
) -> list[ProjectOut]:
    rows = db.scalars(
        select(ProjectRow)
        .where(ProjectRow.user_id == user.id)
        .order_by(ProjectRow.created_at.desc())
    ).all()
    return [project_out(row, settings, clips=False) for row in rows]


@projects.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str, db: DbSession, user: CurrentUser, settings: Config
) -> ProjectOut:
    return project_out(owned_project(db, user, project_id), settings, clips=True)


@projects.get("/{project_id}/clips", response_model=list[ClipOut])
def list_clips(
    project_id: str, db: DbSession, user: CurrentUser, settings: Config
) -> list[ClipOut]:
    row = owned_project(db, user, project_id)
    return [clip_out(item, settings) for item in row.clips]


@projects.get("/{project_id}/jobs", response_model=list[JobOut])
def list_jobs(project_id: str, db: DbSession, user: CurrentUser) -> list[JobOut]:
    row = owned_project(db, user, project_id)
    return [item for item in (job_out(job) for job in row.jobs) if item is not None]


@projects.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str, db: DbSession, user: CurrentUser, settings: Config
) -> Response:
    row = owned_project(db, user, project_id)
    store = get_blob_store(settings)
    for blob in store.list(f"renders/{row.id}/"):
        store.delete(blob.key)
    if row.source_key:
        store.delete(row.source_key)
    db.delete(row)
    return Response(status_code=204)


files = APIRouter(tags=["files"])


@files.get("/files/{token}", response_model=None)
def download_file(token: str, settings: Config) -> Response:
    """Serve a render via a signed, expiring link (usable in <video src>)."""
    payload = unsign(token, settings.secret_key)
    if not payload or payload.get("typ") != "dl":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Link expired or invalid.")
    key = str(payload.get("k"))
    store = get_blob_store(settings)
    url = store.presigned_url(key, 600)
    if url:
        return RedirectResponse(url, status_code=307)
    path = store.local_path(key)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    return FileResponse(path, media_type="video/mp4", filename=Path(key).name)


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    cfg = settings or get_api_settings()
    application = FastAPI(title="Snipzo API", version=__version__)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["meta"])
    def health(db: DbSession) -> dict[str, object]:
        users = db.scalar(select(func.count()).select_from(User)) or 0
        return {"status": "ok", "version": __version__, "users": users}

    application.include_router(auth)
    application.include_router(projects)
    application.include_router(files)
    return application


app = create_app()
