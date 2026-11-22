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
    source_title: str | None = None
    source_thumbnail_url: str | None = None
    source_page_url: str | None = None
    duration_seconds: float | None = None
    rights_confirmed: bool
    source_available: bool
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    job: JobOut | None = None
    clips: list[ClipOut] = Field(default_factory=list)


class CaptionLineIO(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = Field(max_length=200)


class ClipEditIn(BaseModel):
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    hook_title: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    hashtags: list[str] | None = Field(default=None, max_length=30)
    style_id: str | None = None
    captions: list[CaptionLineIO] | None = Field(default=None, max_length=400)
    rerender: bool = True


class ClipEditorOut(BaseModel):
    project_id: str
    clip: ClipOut
    captions: list[CaptionLineIO]
    captions_edited: bool
    styles: list[str]
    source_duration: float
    source_url: str | None = None
    job: JobOut | None = None


class ClipEditResult(BaseModel):
    clip: ClipOut
    trimmed: bool
    job: JobOut | None = None
