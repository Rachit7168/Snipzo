"""Request and response models for the HTTP API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    name: str | None = Field(default=None, max_length=200)


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    plan: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    stage: str | None = None
    progress: float
    message: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ClipOut(BaseModel):
    clip_id: str
    rank: int
    start: float
    end: float
    duration: float
    score: float
    reason: str
    hook_title: str | None = None
    title: str | None = None
    description: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    style_id: str
    render_version: int | None = None
    download_url: str | None = None


class ProjectOut(BaseModel):
    id: str
    title: str | None = None
    status: str
    source_kind: str
    source_filename: str | None = None
    duration_seconds: float | None = None
    rights_confirmed: bool
    source_available: bool
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    job: JobOut | None = None
    clips: list[ClipOut] = Field(default_factory=list)
