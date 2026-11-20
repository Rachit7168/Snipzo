"""Shared data models for Snipzo projects and pipeline artifacts."""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

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

    @property
    def clips_path(self) -> Path:
        return self.root / "clips.json"

    @property
    def crops_dir(self) -> Path:
        return self.root / "crops"

    @property
    def renders_dir(self) -> Path:
        return self.root / "renders"

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


class Clip(BaseModel):
    """A scored highlight window, aligned to sentence boundaries."""

    id: str
    start: float
    end: float
    score: float
    reason: str
    hook_strength: float | None = None
    standalone_clarity: float | None = None
    emotion: float | None = None
    length_score: float | None = None
    hook_title: str | None = None
    style_id: str = "default"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class ClipSet(BaseModel):
    """Selected clips for a project."""

    clips: list[Clip] = Field(default_factory=list)
    prompt_version: str | None = None
    scorer: str = "heuristic"
    min_clip_seconds: float | None = None
    max_clip_seconds: float | None = None


class CropKeyframe(BaseModel):
    """A 9:16 crop window at a point in the source video."""

    t: float
    x: float
    y: float
    w: float
    h: float


class CropPath(BaseModel):
    """Keyframe crop path for one clip, plus the framing mode."""

    clip_id: str
    mode: Literal["face", "center", "blur"]
    keyframes: list[CropKeyframe] = Field(default_factory=list)
    source_width: int
    source_height: int


class Render(BaseModel):
    """A finished vertical Short exported from a clip."""

    clip_id: str
    path: Path
    width: int = 1080
    height: int = 1920
    fps: float = 30
    duration: float
    style_id: str = "bold-yellow"

