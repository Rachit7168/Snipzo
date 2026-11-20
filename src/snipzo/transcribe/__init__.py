"""Speech-to-text with word-level timestamps (Step 3)."""

from snipzo.transcribe.base import Transcriber
from snipzo.transcribe.service import get_transcriber, transcribe_project

__all__ = ["Transcriber", "get_transcriber", "transcribe_project"]
