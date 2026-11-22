"""Database tables for users, channels, projects, and pipeline outputs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snipzo.api.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    plan: Mapped[str] = mapped_column(String(32), default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    projects: Mapped[list[ProjectRow]] = relationship(back_populates="user")


class Channel(Base):
    """A connected publishing channel (e.g. a YouTube channel)."""

    __tablename__ = "channels"
    __table_args__ = (UniqueConstraint("provider", "external_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32), default="youtube")
    external_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProjectRow(Base):
    """A source video submitted by a user; `id` matches the pipeline project id."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    source_kind: Mapped[str] = mapped_column(String(16), default="upload")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship(back_populates="projects")
    clips: Mapped[list[ClipRow]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ClipRow.rank"
    )
    jobs: Mapped[list[Job]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Job.created_at",
    )


class TranscriptRow(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    backend: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ClipRow(Base):
    __tablename__ = "clips"
    __table_args__ = (UniqueConstraint("project_id", "clip_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    clip_id: Mapped[str] = mapped_column(String(32))
    rank: Mapped[int] = mapped_column(Integer, default=0)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    hook_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
    style_id: Mapped[str] = mapped_column(String(32), default="bold-yellow")

    project: Mapped[ProjectRow] = relationship(back_populates="clips")
    renders: Mapped[list[RenderRow]] = relationship(
        back_populates="clip", cascade="all, delete-orphan"
    )


class RenderRow(Base):
    __tablename__ = "renders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    clip_row_id: Mapped[str] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"), index=True
    )
    blob_key: Mapped[str] = mapped_column(String(500))
    width: Mapped[int] = mapped_column(Integer, default=1080)
    height: Mapped[int] = mapped_column(Integer, default=1920)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    clip: Mapped[ClipRow] = relationship(back_populates="renders")


class Publication(Base):
    """A clip published (or scheduled) to a channel."""

    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    clip_row_id: Mapped[str] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"), index=True
    )
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(32), default="queued")
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    privacy_status: Mapped[str] = mapped_column(String(16), default="private")
    publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contains_synthetic_media: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Job(Base):
    """A background task run against a project."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), default="pipeline")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    project: Mapped[ProjectRow] = relationship(back_populates="jobs")


class TakedownRequest(Base):
    """A copyright/takedown report about content processed or published by Snipzo."""

    __tablename__ = "takedown_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    reporter_name: Mapped[str] = mapped_column(String(200))
    reporter_email: Mapped[str] = mapped_column(String(320))
    content_url: Mapped[str] = mapped_column(Text)
    original_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UsageEvent(Base):
    """Metered processing usage (minutes per project) for monthly plan limits."""

    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), default="video")
    minutes: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BillingEvent(Base):
    """Processed Stripe webhook event ids for idempotency."""

    __tablename__ = "billing_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    type: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
