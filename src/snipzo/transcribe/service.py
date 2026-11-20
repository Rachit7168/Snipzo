"""Run transcription for a project and persist the transcript."""

from __future__ import annotations

from pathlib import Path

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.models import Project, ProjectStatus, Transcript
from snipzo.projects import get_storage, resolve_project
from snipzo.storage import Storage
from snipzo.transcribe.base import Transcriber
from snipzo.transcribe.deepgram import DeepgramTranscriber
from snipzo.transcribe.faster_whisper import FasterWhisperTranscriber


def get_transcriber(settings: Settings) -> Transcriber:
    """Return the configured transcription backend."""
    if settings.transcriber == "deepgram":
        if not settings.deepgram_api_key:
            raise SnipzoError(
                "SNIPZO_TRANSCRIBER=deepgram requires SNIPZO_DEEPGRAM_API_KEY."
            )
        return DeepgramTranscriber(settings.deepgram_api_key)
    return FasterWhisperTranscriber(model_size=settings.whisper_model)


def transcribe_project(
    ref: str,
    settings: Settings,
    *,
    storage: Storage | None = None,
    transcriber: Transcriber | None = None,
) -> tuple[Project, Transcript]:
    """Transcribe a project's audio and write `transcript.json`."""
    store = storage or get_storage(settings.work_dir)
    project = resolve_project(ref, store)
    audio = project.audio_path
    if not audio.is_file():
        raise SnipzoError(
            f"No extracted audio for project {project.id}; run `snipzo ingest` first."
        )
    backend = transcriber or get_transcriber(settings)
    transcript = backend.transcribe(audio)
    if not transcript.words and not transcript.segments:
        raise SnipzoError(f"Transcription produced no text for project {project.id}.")
    _save_transcript(store, project, transcript)
    updated = project.touch_status(ProjectStatus.TRANSCRIBED).model_copy(
        update={"language": transcript.language}
    )
    store.save_project(updated)
    return updated, transcript


def load_transcript(project: Project) -> Transcript:
    """Load a previously saved transcript."""
    path = project.transcript_path
    if not path.is_file():
        raise SnipzoError(
            f"No transcript for project {project.id}; run `snipzo transcribe` first."
        )
    return Transcript.model_validate_json(path.read_text(encoding="utf-8"))


def _save_transcript(
    storage: Storage, project: Project, transcript: Transcript
) -> Path:
    return storage.write_json(
        project.id, "transcript.json", transcript.model_dump(mode="json")
    )
