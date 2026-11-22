"""Background logic for YouTube imports and publishing."""

from __future__ import annotations

import logging
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from snipzo.api.blobstore import BlobStore, get_blob_store
from snipzo.api.db import session_scope
from snipzo.api.settings import ApiSettings, get_api_settings
from snipzo.api.tables import Channel, ClipRow, Job, Publication, RenderRow
from snipzo.api.youtube import TokenCipher, YouTubeClient, YouTubeError, build_status
from snipzo.errors import SnipzoError

log = logging.getLogger(__name__)


def fresh_access_token(
    channel: Channel, settings: ApiSettings, client: YouTubeClient
) -> str:
    """Return a valid access token, refreshing (and re-encrypting) when expired."""
    cipher = TokenCipher.from_settings(settings)
    access = cipher.decrypt(channel.access_token_enc)
    expires = channel.token_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if access and expires and expires > datetime.now(UTC):
        return access
    refresh = cipher.decrypt(channel.refresh_token_enc)
    if not refresh:
        raise YouTubeError("The channel connection expired; reconnect YouTube.")
    tokens = client.refresh(refresh)
    channel.access_token_enc = cipher.encrypt(tokens.access_token)
    channel.refresh_token_enc = cipher.encrypt(tokens.refresh_token)
    channel.token_expires_at = tokens.expires_at
    return tokens.access_token


def download_owned_video(url: str, dest: Path) -> Path:
    """Fetch a YouTube video with yt-dlp (shared with pasted-URL imports)."""
    from snipzo.api.ytdlp import download_youtube

    settings = get_api_settings()
    return download_youtube(
        url,
        dest,
        max_bytes=settings.max_upload_mb * 2**20,
        timeout=settings.youtube_download_timeout,
    )


def _render_file(store: BlobStore, key: str, scratch: Path) -> Path:
    local = store.local_path(key)
    if local is not None:
        return local
    return store.get_file(key, scratch / Path(key).name)


def run_publish(job_id: str) -> bool:
    """Upload a rendered clip to the connected channel (videos.insert)."""
    settings = get_api_settings()
    store = get_blob_store(settings)
    scratch = Path(tempfile.mkdtemp(prefix="snipzo-pub-"))
    publication_id = ""
    try:
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is None:
                return False
            publication_id = str(job.payload.get("publication_id", ""))
            publication = session.get(Publication, publication_id)
            if publication is None:
                raise SnipzoError("Publication not found.")
            channel = session.get(Channel, publication.channel_id)
            clip = session.get(ClipRow, publication.clip_row_id)
            if channel is None or clip is None:
                raise SnipzoError("Channel or clip no longer exists.")
            render: RenderRow | None = (
                max(clip.renders, key=lambda item: item.version)
                if clip.renders
                else None
            )
            if render is None:
                raise SnipzoError("This clip has no rendered video yet.")
            job.status = "running"
            job.stage = "publish"
            publication.status = "uploading"
            client = YouTubeClient(settings)
            access = fresh_access_token(channel, settings, client)
            raw_tags = job.payload.get("tags")
            tag_list = (
                [str(tag) for tag in raw_tags]
                if isinstance(raw_tags, list) and raw_tags
                else list(clip.hashtags or [])
            )
            snippet = {
                "title": str(
                    job.payload.get("title") or clip.title or clip.hook_title or "Short"
                )[:100],
                "description": str(
                    job.payload.get("description") or clip.description or ""
                ),
                "tags": [tag.lstrip("#") for tag in tag_list][:30],
                "categoryId": str(job.payload.get("category_id") or "22"),
            }
            status = build_status(
                privacy_status=publication.privacy_status,
                publish_at=publication.publish_at,
                made_for_kids=bool(job.payload.get("made_for_kids", False)),
                contains_synthetic_media=publication.contains_synthetic_media,
            )
            blob_key = render.blob_key

        path = _render_file(store, blob_key, scratch)
        video_id = client.upload_video(access, path, snippet=snippet, status=status)
        with session_scope() as session:
            publication = session.get(Publication, publication_id)
            job = session.get(Job, job_id)
            if publication is not None:
                publication.external_id = video_id
                publication.status = (
                    "scheduled" if publication.publish_at else "published"
                )
            if job is not None:
                job.status = "succeeded"
                job.progress = 1.0
                job.message = f"Uploaded to YouTube as {video_id}."
        return True
    except Exception as exc:
        log.exception("publish failed for job %s", job_id)
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:4000]
            publication = (
                session.get(Publication, publication_id) if publication_id else None
            )
            if publication is not None:
                publication.status = "failed"
                publication.error = str(exc)[:4000]
        return False
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
