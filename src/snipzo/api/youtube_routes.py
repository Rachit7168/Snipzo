"""YouTube endpoints: connect a channel, list/import owned videos, publish clips."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from snipzo.api import billing
from snipzo.api.deps import Config, CurrentUser, DbSession
from snipzo.api.security import sign, unsign
from snipzo.api.tables import Channel, ClipRow, Job, ProjectRow, Publication, User
from snipzo.api.youtube import (
    TokenCipher,
    YouTubeClient,
    YouTubeError,
    authorization_url,
    is_configured,
)
from snipzo.errors import SnipzoError
from snipzo.ingest.service import new_project_id

router = APIRouter(tags=["youtube"])


class ChannelOut(BaseModel):
    id: str
    provider: str
    external_id: str
    title: str | None
    connected_at: datetime


class YouTubeStatusOut(BaseModel):
    configured: bool
    import_enabled: bool
    channels: list[ChannelOut]


class OwnedVideoOut(BaseModel):
    id: str
    title: str
    published_at: str | None = None
    thumbnail: str | None = None


class ImportIn(BaseModel):
    video_id: str = Field(min_length=3, max_length=64)
    rights_confirmed: bool = False


class PublishIn(BaseModel):
    channel_id: str
    title: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = Field(default=None, max_length=30)
    privacy_status: Literal["private", "unlisted", "public"] = "private"
    publish_at: datetime | None = None
    contains_synthetic_media: bool = False
    made_for_kids: bool = False
    rights_confirmed: bool = False


class PublicationOut(BaseModel):
    id: str
    clip_id: str
    channel_id: str
    status: str
    external_id: str | None
    url: str | None
    privacy_status: str
    publish_at: datetime | None
    contains_synthetic_media: bool
    error: str | None
    created_at: datetime


def _channel_out(channel: Channel) -> ChannelOut:
    return ChannelOut(
        id=channel.id,
        provider=channel.provider,
        external_id=channel.external_id,
        title=channel.title,
        connected_at=channel.created_at,
    )


def _owned_channel(db: DbSession, user: User, channel_id: str) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None or channel.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel not found.")
    return channel


def _yt_error(exc: YouTubeError) -> HTTPException:
    return HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))


@router.get("/youtube/status", response_model=YouTubeStatusOut)
def youtube_status(
    db: DbSession, user: CurrentUser, settings: Config
) -> YouTubeStatusOut:
    channels = db.scalars(select(Channel).where(Channel.user_id == user.id)).all()
    return YouTubeStatusOut(
        configured=is_configured(settings),
        import_enabled=settings.youtube_import_downloader != "disabled",
        channels=[_channel_out(item) for item in channels],
    )


@router.get("/youtube/connect")
def youtube_connect(user: CurrentUser, settings: Config) -> dict[str, str]:
    """Return the Google consent URL (state is signed and expires in 10 minutes)."""
    state = sign({"sub": user.id, "typ": "oauth"}, settings.secret_key, 600)
    try:
        return {"auth_url": authorization_url(settings, state)}
    except YouTubeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/youtube/callback", response_model=None)
def youtube_callback(
    db: DbSession,
    settings: Config,
    state: str,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Google redirects here; store the channel with encrypted tokens."""
    back = f"{settings.web_app_url.rstrip('/')}/channels"
    payload = unsign(state, settings.secret_key)
    if not payload or payload.get("typ") != "oauth":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired state.")
    if error or not code:
        return RedirectResponse(f"{back}?error={error or 'cancelled'}", status_code=303)
    user = db.get(User, str(payload.get("sub")))
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown user.")
    client = YouTubeClient(settings)
    try:
        tokens = client.exchange_code(code)
        info = client.my_channel(tokens.access_token)
    except YouTubeError as exc:
        raise _yt_error(exc) from exc
    cipher = TokenCipher.from_settings(settings)
    channel = db.scalar(
        select(Channel).where(
            Channel.provider == "youtube", Channel.external_id == info.id
        )
    )
    if channel is not None and channel.user_id != user.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This channel is connected to another account."
        )
    if channel is None:
        channel = Channel(user_id=user.id, provider="youtube", external_id=info.id)
        db.add(channel)
    channel.title = info.title
    channel.access_token_enc = cipher.encrypt(tokens.access_token)
    if tokens.refresh_token:
        channel.refresh_token_enc = cipher.encrypt(tokens.refresh_token)
    channel.token_expires_at = tokens.expires_at
    db.commit()
    return RedirectResponse(f"{back}?connected=1", status_code=303)


@router.delete("/youtube/channels/{channel_id}", status_code=204, response_model=None)
def youtube_disconnect(channel_id: str, db: DbSession, user: CurrentUser) -> None:
    db.delete(_owned_channel(db, user, channel_id))


@router.get("/youtube/channels/{channel_id}/videos", response_model=list[OwnedVideoOut])
def youtube_videos(
    channel_id: str, db: DbSession, user: CurrentUser, settings: Config
) -> list[OwnedVideoOut]:
    """Videos from the channel's own uploads playlist (owned by definition)."""
    from snipzo.api.publishing import fresh_access_token

    channel = _owned_channel(db, user, channel_id)
    client = YouTubeClient(settings)
    try:
        access = fresh_access_token(channel, settings, client)
        info = client.my_channel(access)
        if info.id != channel.external_id or not info.uploads_playlist:
            raise YouTubeError("Connected account no longer matches this channel.")
        videos = client.list_uploads(access, info.uploads_playlist)
    except YouTubeError as exc:
        raise _yt_error(exc) from exc
    return [
        OwnedVideoOut(
            id=video.id,
            title=video.title,
            published_at=video.published_at,
            thumbnail=video.thumbnail,
        )
        for video in videos
        if not video.channel_id or video.channel_id == channel.external_id
    ]


@router.post("/youtube/channels/{channel_id}/import", status_code=201)
def youtube_import(
    channel_id: str, body: ImportIn, db: DbSession, user: CurrentUser, settings: Config
) -> dict[str, str]:
    """Import a video only after confirming it belongs to the connected channel."""
    from snipzo.api.app import enqueue
    from snipzo.api.publishing import fresh_access_token

    if not body.rights_confirmed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Confirm that you own or have rights to this content.",
        )
    channel = _owned_channel(db, user, channel_id)
    client = YouTubeClient(settings)
    try:
        access = fresh_access_token(channel, settings, client)
        video = client.get_video(access, body.video_id)
    except YouTubeError as exc:
        raise _yt_error(exc) from exc
    if video is None or video.channel_id != channel.external_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only import videos uploaded to your connected channel.",
        )
    try:
        billing.check_can_start_video(db, user, settings)
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc
    if settings.youtube_import_downloader == "disabled":
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Ownership verified, but YouTube import is turned off on this server. "
            "Upload the original file instead.",
        )
    from snipzo.api.ytdlp import probe_youtube
    from snipzo.youtube_url import canonical_watch_url, default_thumbnail_url

    watch_url = canonical_watch_url(video.id)
    source_title = video.title[:300]
    source_thumb = default_thumbnail_url(video.id)
    duration = None
    try:
        info = probe_youtube(watch_url)
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    source_title = info.title or source_title
    source_thumb = info.thumbnail_url or source_thumb
    duration = info.duration
    try:
        if duration:
            billing.check_minutes(db, user, settings, duration / 60.0)
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc
    project_id = new_project_id()
    db.add(
        ProjectRow(
            id=project_id,
            user_id=user.id,
            title=source_title,
            status="queued",
            source_kind="youtube",
            source_url=watch_url,
            source_filename=f"{video.id}.mp4",
            source_title=source_title,
            source_thumbnail_url=source_thumb,
            duration_seconds=duration,
            rights_confirmed=True,
        )
    )
    job = Job(project_id=project_id, kind="pipeline", status="queued")
    db.add(job)
    db.commit()
    enqueue(job.id)
    return {"project_id": project_id}


def _publication_out(pub: Publication, clip_id: str) -> PublicationOut:
    url = f"https://youtube.com/shorts/{pub.external_id}" if pub.external_id else None
    return PublicationOut(
        id=pub.id,
        clip_id=clip_id,
        channel_id=pub.channel_id,
        status=pub.status,
        external_id=pub.external_id,
        url=url,
        privacy_status=pub.privacy_status,
        publish_at=pub.publish_at,
        contains_synthetic_media=pub.contains_synthetic_media,
        error=pub.error,
        created_at=pub.created_at,
    )


@router.post(
    "/projects/{project_id}/clips/{clip_id}/publish",
    response_model=PublicationOut,
    status_code=201,
)
def publish_clip(
    project_id: str,
    clip_id: str,
    body: PublishIn,
    db: DbSession,
    user: CurrentUser,
) -> PublicationOut:
    """Queue a `videos.insert` upload of the latest render (optionally scheduled)."""
    from snipzo.api.worker import enqueue_publish

    project = db.get(ProjectRow, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    if not body.rights_confirmed or not project.rights_confirmed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Confirm that you own or have rights to publish this content.",
        )
    channel = _owned_channel(db, user, body.channel_id)
    clip = db.scalar(
        select(ClipRow).where(
            ClipRow.project_id == project_id, ClipRow.clip_id == clip_id
        )
    )
    if clip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clip not found.")
    if not clip.renders:
        raise HTTPException(status.HTTP_409_CONFLICT, "Render the clip first.")
    publish_at = body.publish_at
    if publish_at is not None:
        if publish_at.tzinfo is None:
            publish_at = publish_at.replace(tzinfo=UTC)
        if publish_at < datetime.now(UTC) + timedelta(minutes=15):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Schedule at least 15 minutes in the future.",
            )
    pub = Publication(
        clip_row_id=clip.id,
        channel_id=channel.id,
        status="queued",
        privacy_status="private" if publish_at else body.privacy_status,
        publish_at=publish_at,
        contains_synthetic_media=body.contains_synthetic_media,
    )
    db.add(pub)
    db.flush()
    job = Job(
        project_id=project_id,
        kind="publish",
        status="queued",
        stage="publish",
        payload={
            "publication_id": pub.id,
            "clip_id": clip_id,
            "title": body.title,
            "description": body.description,
            "tags": body.tags,
            "made_for_kids": body.made_for_kids,
        },
    )
    db.add(job)
    db.commit()
    enqueue_publish(job.id)
    db.expire_all()
    fresh = db.get(Publication, pub.id)
    assert fresh is not None
    return _publication_out(fresh, clip_id)


@router.get("/projects/{project_id}/publications", response_model=list[PublicationOut])
def list_publications(
    project_id: str, db: DbSession, user: CurrentUser
) -> list[PublicationOut]:
    project = db.get(ProjectRow, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    out: list[PublicationOut] = []
    for clip in project.clips:
        pubs = db.scalars(
            select(Publication)
            .where(Publication.clip_row_id == clip.id)
            .order_by(Publication.created_at)
        ).all()
        out.extend(_publication_out(pub, clip.clip_id) for pub in pubs)
    return out
