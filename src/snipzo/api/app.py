"""FastAPI application: auth, uploads, job status, clips, and downloads."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import secrets
import shutil
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from snipzo import __version__
from snipzo.api import billing, jobs, mailer
from snipzo.api.billing_routes import router as billing_router
from snipzo.api.blobstore import get_blob_store, source_key
from snipzo.api.deps import Config, CurrentUser, DbSession
from snipzo.api.schemas import (
    CaptionLineIO,
    ChangePasswordIn,
    ClipEditIn,
    ClipEditorOut,
    ClipEditResult,
    ClipOut,
    Credentials,
    DeleteAccountRequestIn,
    ForgotPasswordIn,
    JobOut,
    MessageOut,
    ProfileUpdateIn,
    ProjectOut,
    ResendVerificationOut,
    ResetPasswordIn,
    TokenOut,
    UserOut,
    VerifyEmailIn,
    VerifyEmailOut,
)
from snipzo.api.security import hash_password, sign, unsign, verify_password
from snipzo.api.settings import ApiSettings, get_api_settings
from snipzo.api.tables import (
    AccountToken,
    ClipRow,
    Job,
    ProjectRow,
    TakedownRequest,
    User,
)
from snipzo.api.youtube_routes import router as youtube_router
from snipzo.errors import SnipzoError
from snipzo.ingest.service import new_project_id

ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
log = logging.getLogger(__name__)


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        plan=user.plan,
        email_verified=bool(user.email_verified),
        deletion_requested_at=user.deletion_requested_at,
        created_at=user.created_at,
    )


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
        source_title=row.source_title,
        source_thumbnail_url=row.source_thumbnail_url,
        source_page_url=row.source_url if row.source_kind == "youtube" else None,
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


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _create_account_token(
    db: DbSession,
    user: User,
    *,
    kind: str,
    target_email: str,
    ttl_seconds: int,
) -> str:
    raw = secrets.token_urlsafe(32)
    row = AccountToken(
        user_id=user.id,
        kind=kind,
        target_email=target_email,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
    )
    db.add(row)
    db.flush()
    return raw


def _consume_account_token(
    db: DbSession, raw: str, *, kind: str
) -> tuple[AccountToken, User]:
    digest = _hash_token(raw.strip())
    token_row = db.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == digest, AccountToken.kind == kind
        )
    )
    if token_row is None or token_row.used_at is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This link is invalid or has already been used.",
        )
    expires = token_row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This link has expired. Request a new one."
        )
    user = db.get(User, token_row.user_id)
    if user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This link is no longer valid."
        )
    token_row.used_at = datetime.now(UTC)
    return token_row, user


def _send_verify_link(
    db: DbSession, user: User, settings: ApiSettings, *, strict: bool = False
) -> None:
    raw = _create_account_token(
        db,
        user,
        kind="verify_email",
        target_email=user.email,
        ttl_seconds=settings.email_verify_ttl_seconds,
    )
    verify_url = f"{settings.web_app_url.rstrip('/')}/verify-email?token={raw}"
    try:
        mailer.send_verification_email(user.email, verify_url, settings)
    except Exception as exc:
        log.exception("Failed to send verification email for user %s", user.id)
        if strict:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Could not send verification email right now. Please try again.",
            ) from exc


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
    _send_verify_link(db, user, settings, strict=False)
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


@auth.patch("/me", response_model=UserOut)
def update_me(
    body: ProfileUpdateIn, db: DbSession, user: CurrentUser, settings: Config
) -> UserOut:
    if body.name is not None:
        cleaned_name = body.name.strip()
        user.name = cleaned_name or None
    if body.email is not None:
        new_email = body.email.strip().lower()
        if "@" not in new_email:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid email.")
        if new_email != user.email:
            if not body.current_password or not verify_password(
                body.current_password, user.password_hash
            ):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Enter your current password to change your email address.",
                )
            existing = db.scalar(select(User).where(User.email == new_email))
            if existing is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Email already registered."
                )
            user.email = new_email
            user.email_verified = False
            user.email_verified_at = None
            db.flush()
            _send_verify_link(db, user, settings, strict=False)
    db.flush()
    return user_out(user)


@auth.post("/change-password", response_model=MessageOut)
def change_password(
    body: ChangePasswordIn, db: DbSession, user: CurrentUser
) -> MessageOut:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Current password is incorrect."
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Choose a new password different from your current one.",
        )
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    db.flush()
    return MessageOut(message="Password updated.")


@auth.post("/verify-email/resend", response_model=ResendVerificationOut)
def resend_verification(
    db: DbSession, user: CurrentUser, settings: Config
) -> ResendVerificationOut:
    if user.email_verified:
        return ResendVerificationOut(sent=False, already_verified=True)
    _send_verify_link(db, user, settings, strict=True)
    return ResendVerificationOut(sent=True, already_verified=False)


@auth.post("/verify-email", response_model=VerifyEmailOut)
def verify_email(body: VerifyEmailIn, db: DbSession) -> VerifyEmailOut:
    token_row, user = _consume_account_token(db, body.token, kind="verify_email")
    if token_row.target_email != user.email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This verification link is for an older email address.",
        )
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    db.flush()
    return VerifyEmailOut(verified=True, email=user.email)


@auth.post("/forgot-password", response_model=MessageOut)
def forgot_password(
    body: ForgotPasswordIn, db: DbSession, settings: Config
) -> MessageOut:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        raw = _create_account_token(
            db,
            user,
            kind="reset_password",
            target_email=user.email,
            ttl_seconds=settings.password_reset_ttl_seconds,
        )
        reset_url = f"{settings.web_app_url.rstrip('/')}/reset-password?token={raw}"
        try:
            mailer.send_password_reset_email(user.email, reset_url, settings)
        except Exception:
            log.exception("Failed to send password reset email for user %s", user.id)
    return MessageOut(
        message=(
            "If an account exists for that email, "
            "we sent password reset instructions."
        )
    )


@auth.post("/reset-password", response_model=MessageOut)
def reset_password(body: ResetPasswordIn, db: DbSession) -> MessageOut:
    _token_row, user = _consume_account_token(db, body.token, kind="reset_password")
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    db.flush()
    return MessageOut(message="Password reset. You can sign in with your new password.")


@auth.post("/delete-request", response_model=UserOut)
def request_account_deletion(
    body: DeleteAccountRequestIn, db: DbSession, user: CurrentUser
) -> UserOut:
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password is incorrect.")
    if user.deletion_requested_at is None:
        user.deletion_requested_at = datetime.now(UTC)
    log.info("Account deletion requested for user %s", user.id)
    db.flush()
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
    """Upload a video, paste a YouTube link, or give a direct file URL."""
    if not rights_confirmed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Confirm that you own or have rights to this content.",
        )
    try:
        billing.check_can_start_video(db, user, settings)
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc
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
            kind, url = jobs.classify_source_url(source_url or "")
        except SnipzoError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        if kind == "youtube":
            _prepare_youtube_project(db, user, settings, row, url)
        else:
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



def _prepare_youtube_project(
    db: DbSession,
    user: User,
    settings: ApiSettings,
    row: ProjectRow,
    url: str,
) -> None:
    """Probe a YouTube URL, enforce plan minutes, and fill preview fields."""
    if settings.youtube_import_downloader == "disabled":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "YouTube import is turned off on this server. Upload the file instead.",
        )
    from snipzo.api.ytdlp import probe_youtube

    try:
        info = probe_youtube(url)
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    try:
        if info.duration:
            billing.check_minutes(db, user, settings, info.duration / 60.0)
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc
    row.source_kind = "youtube"
    row.source_url = info.url
    row.source_filename = f"{info.video_id}.mp4"
    row.source_title = info.title
    row.source_thumbnail_url = info.thumbnail_url
    if info.duration:
        row.duration_seconds = info.duration
    if not row.title:
        row.title = info.title


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


def enqueue_rerender(job_id: str) -> None:
    from snipzo.api.worker import enqueue_rerender as _enqueue

    _enqueue(job_id)


def _clip_row(db: DbSession, project_id: str, clip_id: str) -> ClipRow:
    row = db.scalar(
        select(ClipRow).where(
            ClipRow.project_id == project_id, ClipRow.clip_id == clip_id
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clip not found.")
    return row


def _latest_clip_job(project: ProjectRow, clip_id: str) -> Job | None:
    matches = [
        job
        for job in project.jobs
        if job.kind == "rerender" and job.payload.get("clip_id") == clip_id
    ]
    return matches[-1] if matches else None


@projects.get("/{project_id}/clips/{clip_id}/editor", response_model=ClipEditorOut)
def clip_editor(
    project_id: str, clip_id: str, db: DbSession, user: CurrentUser, settings: Config
) -> ClipEditorOut:
    """Everything the editor needs: trim, captions, styles, and a source preview."""
    from snipzo.edit import editor_state

    project = owned_project(db, user, project_id)
    row = _clip_row(db, project_id, clip_id)
    try:
        state = editor_state(project_id, clip_id, jobs.pipeline_settings())
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    source_url = None
    if project.source_key and project.source_deleted_at is None:
        source_url = download_link(project.source_key, settings)
    return ClipEditorOut(
        project_id=project_id,
        clip=clip_out(row, settings),
        captions=[CaptionLineIO(**line.model_dump()) for line in state.captions],
        captions_edited=state.captions_edited,
        styles=state.styles,
        source_duration=state.source_duration,
        source_url=source_url,
        job=job_out(_latest_clip_job(project, clip_id)),
    )


@projects.patch("/{project_id}/clips/{clip_id}", response_model=ClipEditResult)
def edit_clip(
    project_id: str,
    clip_id: str,
    body: ClipEditIn,
    db: DbSession,
    user: CurrentUser,
    settings: Config,
) -> ClipEditResult:
    """Save trim/caption/title/style edits and (by default) queue a re-render."""
    from snipzo.edit import CaptionLine, ClipEdit, apply_clip_edit, load_metadata
    from snipzo.projects import get_storage, resolve_project

    project = owned_project(db, user, project_id)
    row = _clip_row(db, project_id, clip_id)
    if body.rerender and project.source_deleted_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The source video was deleted after the retention window.",
        )
    edit = ClipEdit(
        start=body.start,
        end=body.end,
        hook_title=body.hook_title,
        title=body.title,
        description=body.description,
        hashtags=body.hashtags,
        style_id=body.style_id,
        captions=(
            [CaptionLine(**line.model_dump()) for line in body.captions]
            if body.captions is not None
            else None
        ),
    )
    pipeline = jobs.pipeline_settings()
    try:
        clip, trimmed = apply_clip_edit(project_id, clip_id, edit, pipeline)
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    row.start = clip.start
    row.end = clip.end
    row.hook_title = clip.hook_title
    if body.style_id is not None:
        row.style_id = body.style_id
    meta = load_metadata(
        resolve_project(project_id, get_storage(pipeline.work_dir)), clip_id
    )
    if meta is not None:
        row.title = meta.title
        row.description = meta.description
        row.hashtags = list(meta.hashtags)

    job: Job | None = None
    if body.rerender:
        job = Job(
            project_id=project_id,
            kind="rerender",
            status="queued",
            stage="render",
            payload={"clip_id": clip_id, "reframe": trimmed},
            message=f"Queued re-render of {clip_id}.",
        )
        db.add(job)
    db.commit()
    if job is not None:
        enqueue_rerender(job.id)
    db.expire_all()
    fresh_row = _clip_row(db, project_id, clip_id)
    fresh_job = db.get(Job, job.id) if job is not None else None
    return ClipEditResult(
        clip=clip_out(fresh_row, settings), trimmed=trimmed, job=job_out(fresh_job)
    )


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
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=Path(key).name)


legal = APIRouter(tags=["legal"])


class TakedownIn(BaseModel):
    reporter_name: str = Field(min_length=2, max_length=200)
    reporter_email: str = Field(min_length=3, max_length=320)
    content_url: str = Field(min_length=5, max_length=2000)
    original_url: str | None = Field(default=None, max_length=2000)
    details: str = Field(min_length=10, max_length=5000)
    good_faith: bool = False


@legal.post("/takedown", status_code=201)
def submit_takedown(body: TakedownIn, db: DbSession) -> dict[str, str]:
    """Record a takedown request (reviewed by the operator; see docs/TAKEDOWN.md)."""
    if not body.good_faith or "@" not in body.reporter_email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A valid email and the good-faith statement are required.",
        )
    item = TakedownRequest(
        reporter_name=body.reporter_name,
        reporter_email=body.reporter_email.strip(),
        content_url=body.content_url,
        original_url=body.original_url,
        details=body.details,
    )
    db.add(item)
    db.flush()
    return {"id": item.id, "status": item.status}


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    cfg = settings or get_api_settings()
    application = FastAPI(title="Snipzo API", version=__version__)

    @application.middleware("http")
    async def attach_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", request_id)
        return response

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex[:12]
        log.exception(
            "Unhandled error [request_id=%s] %s %s",
            request_id,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Something went wrong on our side. Please try again.",
                "request_id": request_id,
            },
            headers={"X-Request-Id": request_id},
        )

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
    application.include_router(youtube_router)
    application.include_router(billing_router)
    application.include_router(legal)
    return application


app = create_app()
