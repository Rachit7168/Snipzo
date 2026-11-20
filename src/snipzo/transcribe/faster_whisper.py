"""faster-whisper transcription backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, cast

from snipzo.errors import SnipzoError
from snipzo.models import Segment, Transcript, Word


class _WhisperModel(Protocol):
    def transcribe(
        self,
        audio: str | object,
        word_timestamps: bool = False,
        vad_filter: bool = False,
    ) -> tuple[Any, Any]: ...


class FasterWhisperTranscriber:
    """Local transcription via faster-whisper (CTranslate2)."""

    def __init__(self, model_size: str = "base", device: str = "auto") -> None:
        self.model_size = model_size
        self.device = device
        self._model: _WhisperModel | None = None

    def transcribe(self, audio_path: Path) -> Transcript:
        model = self._load()
        audio = load_pcm16_wav(audio_path)
        segments_iter, info = model.transcribe(
            audio,
            word_timestamps=True,
            vad_filter=True,
        )
        segments: list[Segment] = []
        words: list[Word] = []
        for raw in segments_iter:
            raw_words = getattr(raw, "words", None) or []
            segment_words = [_word(item) for item in raw_words]
            text = str(getattr(raw, "text", "")).strip()
            if not text and segment_words:
                text = " ".join(word.text for word in segment_words)
            segment = Segment(
                start=float(getattr(raw, "start", 0.0) or 0.0),
                end=float(getattr(raw, "end", 0.0) or 0.0),
                text=text,
                words=segment_words,
                confidence=_optional_float(getattr(raw, "avg_logprob", None)),
            )
            segments.append(segment)
            words.extend(segment_words)

        duration = max(
            (_optional_float(getattr(info, "duration", None)) or 0.0),
            words[-1].end if words else 0.0,
            segments[-1].end if segments else 0.0,
        )
        language = str(getattr(info, "language", None) or "en")
        return Transcript(
            language=language,
            duration=duration,
            segments=segments,
            words=words or _words_from_segments(segments),
            backend="faster-whisper",
            model=self.model_size,
        )

    def _load(self) -> _WhisperModel:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SnipzoError(
                "faster-whisper is not installed. Run: pip install -e '.[pipeline]'"
            ) from exc
        device, compute_type = _device_and_compute(self.device)
        self._model = cast(
            _WhisperModel,
            WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            ),
        )
        return self._model


def _device_and_compute(device: str) -> tuple[str, str]:
    if device == "auto":
        return "cpu", "int8"
    if device == "cuda":
        return "cuda", "float16"
    return device, "int8"


def _word(item: object) -> Word:
    return Word(
        text=str(getattr(item, "word", getattr(item, "text", ""))).strip(),
        start=float(getattr(item, "start", 0.0) or 0.0),
        end=float(getattr(item, "end", 0.0) or 0.0),
        confidence=_optional_float(getattr(item, "probability", None)),
    )


def _words_from_segments(segments: list[Segment]) -> list[Word]:
    words: list[Word] = []
    for segment in segments:
        words.extend(segment.words)
    return words


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def load_pcm16_wav(path: Path) -> object:
    """Load a PCM WAV as float32 samples so we do not depend on PyAV."""
    import wave

    import numpy as np

    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            frames = handle.readframes(handle.getnframes())
    except wave.Error as exc:
        raise SnipzoError(f"Could not read WAV audio: {path}") from exc
    if sample_width != 2:
        raise SnipzoError(
            f"Expected 16-bit PCM audio, got {sample_width * 8}-bit: {path}"
        )
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio

