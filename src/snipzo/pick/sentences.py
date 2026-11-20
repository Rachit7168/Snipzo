"""Split a word-level transcript into sentences and topic chunks."""

from __future__ import annotations

import re
from collections.abc import Sequence

from snipzo.models import Segment, Transcript, Word

_SENTENCE_END = re.compile(r"[.!?…][\"')\]]*$")
_TOKEN = re.compile(r"[a-z0-9]+")
_PAUSE_S = 0.7


def words_from_transcript(transcript: Transcript) -> list[Word]:
    """Return a flat word list, falling back to segment words if needed."""
    if transcript.words:
        return list(transcript.words)
    words: list[Word] = []
    for segment in transcript.segments:
        words.extend(segment.words)
    return words


def sentences_from_transcript(transcript: Transcript) -> list[Segment]:
    """Group words into sentences using punctuation and pauses."""
    words = words_from_transcript(transcript)
    if not words:
        return list(transcript.segments)

    sentences: list[Segment] = []
    current: list[Word] = []
    for index, word in enumerate(words):
        if current and (word.start - current[-1].end) >= _PAUSE_S:
            sentences.append(_segment_from_words(current))
            current = []
        current.append(word)
        next_word = words[index + 1] if index + 1 < len(words) else None
        gap = 0.0 if next_word is None else max(0.0, next_word.start - word.end)
        if _SENTENCE_END.search(word.text.strip()) and (
            next_word is None or gap >= 0.05
        ):
            sentences.append(_segment_from_words(current))
            current = []
    if current:
        sentences.append(_segment_from_words(current))
    return [sentence for sentence in sentences if sentence.text.strip()]


def topic_chunks(
    sentences: Sequence[Segment], scene_cuts: Sequence[float] | None = None
) -> list[Segment]:
    """Group sentences into topic chunks using lexical similarity and scene cuts."""
    if not sentences:
        return []
    cuts = sorted(scene_cuts or [])
    chunks: list[Segment] = []
    current = [sentences[0]]
    for previous, sentence in zip(sentences, sentences[1:], strict=False):
        low = previous.end
        high = sentence.start
        crossed_cut = any(low < cut <= high or abs(cut - high) <= 0.15 for cut in cuts)
        similar = _jaccard(previous.text, sentence.text) >= 0.12
        gap = sentence.start - previous.end
        too_long = (sentence.end - current[0].start) > 60
        if crossed_cut or gap >= 1.2 or too_long or not similar:
            chunks.append(_merge(current))
            current = [sentence]
        else:
            current.append(sentence)
    if current:
        chunks.append(_merge(current))
    return chunks


def snap_to_sentences(
    start: float,
    end: float,
    sentences: Sequence[Segment],
    *,
    duration: float,
    pad: float = 0.2,
) -> tuple[float, float]:
    """Snap a window to sentence boundaries and apply padding, never mid-word."""
    if not sentences:
        snapped_start = max(0.0, start - pad)
        snapped_end = min(duration, max(end, snapped_start + 0.5) + pad)
        return round(snapped_start, 3), round(min(duration, snapped_end), 3)

    start_sentence = sentences[0]
    for sentence in sentences:
        if sentence.start <= start + 0.05:
            start_sentence = sentence
        else:
            break
    # If the requested start is clearly in the gap before the next sentence, use it.
    next_index = sentences.index(start_sentence) + 1
    if (
        next_index < len(sentences)
        and start >= start_sentence.end
        and abs(sentences[next_index].start - start)
        <= abs(start_sentence.start - start)
    ):
        start_sentence = sentences[next_index]

    end_sentence = start_sentence
    for sentence in sentences:
        if sentence.start < start_sentence.start:
            continue
        end_sentence = sentence
        if sentence.end >= end - 0.05:
            break

    snapped_start = max(0.0, start_sentence.start - pad)
    snapped_end = min(duration, end_sentence.end + pad)
    if snapped_end <= snapped_start:
        snapped_end = min(duration, start_sentence.end + pad)
    return round(snapped_start, 3), round(snapped_end, 3)


def _segment_from_words(words: list[Word]) -> Segment:
    text = re.sub(r"\s+", " ", " ".join(word.text for word in words)).strip()
    return Segment(
        start=words[0].start,
        end=words[-1].end,
        text=text,
        words=list(words),
    )


def _merge(parts: Sequence[Segment]) -> Segment:
    words: list[Word] = []
    for part in parts:
        words.extend(part.words)
    if words:
        return _segment_from_words(words)
    return Segment(
        start=parts[0].start,
        end=parts[-1].end,
        text=" ".join(part.text for part in parts).strip(),
        words=[],
    )


def _jaccard(left: str, right: str) -> float:
    left_tokens = set(_TOKEN.findall(left.lower()))
    right_tokens = set(_TOKEN.findall(right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
