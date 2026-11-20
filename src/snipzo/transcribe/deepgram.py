"""Optional Deepgram hosted transcription backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from snipzo.errors import SnipzoError
from snipzo.models import Segment, Transcript, Word

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true&utterances=true"


class DeepgramTranscriber:
    """Hosted transcriber using the Deepgram pre-recorded API."""

    def __init__(self, api_key: str, timeout: float = 120.0) -> None:
        if not api_key:
            raise SnipzoError("Deepgram backend requires SNIPZO_DEEPGRAM_API_KEY.")
        self.api_key = api_key
        self.timeout = timeout

    def transcribe(self, audio_path: Path) -> Transcript:
        payload = _request(
            audio_path,
            api_key=self.api_key,
            timeout=self.timeout,
        )
        hint = _wav_duration_hint(audio_path)
        return parse_deepgram_response(payload, duration_hint=hint)


def parse_deepgram_response(
    payload: dict[str, Any], *, duration_hint: float = 0.0
) -> Transcript:
    """Convert a Deepgram listen response into a Transcript (also used by tests)."""
    results = payload.get("results") or {}
    channels = results.get("channels") or []
    if not channels:
        raise SnipzoError("Deepgram response did not include any channels.")
    alternative = (channels[0].get("alternatives") or [{}])[0]
    raw_words = alternative.get("words") or []
    words = [
        Word(
            text=str(item.get("punctuated_word") or item.get("word") or "").strip(),
            start=float(item.get("start") or 0.0),
            end=float(item.get("end") or 0.0),
            confidence=_optional_float(item.get("confidence")),
        )
        for item in raw_words
        if str(item.get("punctuated_word") or item.get("word") or "").strip()
    ]
    utterances = results.get("utterances") or []
    segments = _segments_from_utterances(utterances)
    if not segments and alternative.get("transcript"):
        segments = [
            Segment(
                start=words[0].start if words else 0.0,
                end=words[-1].end if words else duration_hint,
                text=str(alternative.get("transcript") or "").strip(),
                words=words,
            )
        ]
    metadata = payload.get("metadata") or {}
    language = (
        str(alternative.get("languages")[0])
        if alternative.get("languages")
        else str(metadata.get("detected_language") or results.get("language") or "en")
    )
    fallback = words[-1].end if words else 0.0
    duration = float(metadata.get("duration") or duration_hint or fallback)
    return Transcript(
        language=language,
        duration=duration,
        segments=segments,
        words=words,
        backend="deepgram",
        model=str((metadata.get("model_info") or {}).get("name") or "nova-2"),
    )


def _segments_from_utterances(utterances: list[dict[str, Any]]) -> list[Segment]:
    segments: list[Segment] = []
    for item in utterances:
        raw_words = item.get("words") or []
        words = [
            Word(
                text=str(word.get("punctuated_word") or word.get("word") or "").strip(),
                start=float(word.get("start") or 0.0),
                end=float(word.get("end") or 0.0),
                confidence=_optional_float(word.get("confidence")),
            )
            for word in raw_words
            if str(word.get("punctuated_word") or word.get("word") or "").strip()
        ]
        text = str(item.get("transcript") or "").strip()
        if not text and words:
            text = " ".join(word.text for word in words)
        if not text:
            continue
        segments.append(
            Segment(
                start=float(item.get("start") or (words[0].start if words else 0.0)),
                end=float(item.get("end") or (words[-1].end if words else 0.0)),
                text=text,
                words=words,
                confidence=_optional_float(item.get("confidence")),
            )
        )
    return segments


def _request(audio_path: Path, *, api_key: str, timeout: float) -> dict[str, Any]:
    data = audio_path.read_bytes()
    request = urllib.request.Request(
        DEEPGRAM_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise SnipzoError(f"Deepgram request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise SnipzoError(f"Deepgram request failed: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise SnipzoError("Deepgram returned an unexpected response.")
    return payload


def _wav_duration_hint(path: Path) -> float:
    # Best-effort; the API metadata is preferred.
    try:
        size = path.stat().st_size
    except OSError:
        return 0.0
    # 16 kHz mono 16-bit PCM plus a ~44 byte header.
    return max(0.0, (size - 44) / (16000 * 2))


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None
