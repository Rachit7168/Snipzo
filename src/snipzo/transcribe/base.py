"""Transcriber protocol shared by local and hosted backends."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from snipzo.models import Transcript


@runtime_checkable
class Transcriber(Protocol):
    """Speech-to-text backend that returns word-level timestamps."""

    def transcribe(self, audio_path: Path) -> Transcript:
        """Transcribe `audio_path` and return segments plus words."""
        ...
