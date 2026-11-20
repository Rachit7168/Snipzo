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

    @property
    def transcript_path(self) -> Path:
        return self.root / "transcript.json"

    def touch_status(self, status: ProjectStatus) -> Self:
        """Return a copy with an updated status and timestamp."""
        return self.model_copy(update={"status": status, "updated_at": utcnow()})


class Word(BaseModel):
    """A single word with timestamps."""

    text: str
    start: float
    end: float
    confidence: float | None = None


class Segment(BaseModel):
    """A transcript segment (typically a phrase or sentence)."""

    start: float
    end: float
    text: str
    words: list[Word] = Field(default_factory=list)
    confidence: float | None = None


class Transcript(BaseModel):
    """Word-level transcript for a project."""

    language: str
    duration: float
    segments: list[Segment] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)
    backend: str | None = None
    model: str | None = None

    def text(self) -> str:
        """Return the full transcript text."""
        if self.segments:
            return " ".join(
                segment.text.strip()
                for segment in self.segments
                if segment.text.strip()
            )
        return " ".join(word.text for word in self.words)

