"""Shared data models for Snipzo projects and pipeline artifacts."""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class ProjectStatus(StrEnum):
    """Pipeline progress for a project."""

    INGESTED = "ingested"
    TRANSCRIBED = "transcribed"
    PICKED = "picked"
    REFRAMED = "reframed"
    RENDERED = "rendered"
    COMPLETE = "complete"


class VideoInfo(BaseModel):
    """Technical metadata from ffprobe."""

    path: Path
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    codec: str | None = None


class Project(BaseModel):
    """A single source video and the artifacts produced from it."""

    id: str
    status: ProjectStatus = ProjectStatus.INGESTED
    source: VideoInfo
    work_dir: Path
    language: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def root(self) -> Path:
        """Directory that holds this project's files."""
        return self.work_dir / self.id

    @property
    def source_path(self) -> Path:
        return self.root / Path(self.source.path).name

    @property
    def audio_path(self) -> Path:
        return self.root / "audio.wav"

    @property
    def project_json_path(self) -> Path:
        return self.root / "project.json"

    def touch_status(self, status: ProjectStatus) -> Self:
        """Return a copy with an updated status and timestamp."""
        return self.model_copy(update={"status": status, "updated_at": utcnow()})
