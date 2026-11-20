"""Build sentence-aligned highlight candidate windows."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from snipzo.models import Segment
from snipzo.pick.sentences import snap_to_sentences


class Candidate(BaseModel):
    """A sentence-aligned window that can be scored."""

    id: str
    start: float
    end: float
    text: str
    sentences: list[Segment] = Field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def clip_length_bounds(
    duration: float, min_seconds: float = 20.0, max_seconds: float = 60.0
) -> tuple[float, float]:
    """Adapt 20-60s targets when the source is shorter than the minimum."""
    if duration <= 0:
        return 0.0, 0.0
    if duration < min_seconds:
        return max(1.0, min(duration, duration * 0.4)), duration
    return min_seconds, min(max_seconds, duration)


def build_candidates(
    sentences: Sequence[Segment],
    *,
    duration: float,
    min_seconds: float = 20.0,
    max_seconds: float = 60.0,
    pad: float = 0.2,
    topic_starts: Sequence[float] | None = None,
    max_candidates: int = 30,
) -> list[Candidate]:
    """Build de-duplicated candidate windows on sentence boundaries."""
    if not sentences:
        return []
    min_s, max_s = clip_length_bounds(duration, min_seconds, max_seconds)
    preferred = {round(value, 3) for value in (topic_starts or [])}
    start_indices = _start_indices(sentences, preferred)
    raw: list[tuple[int, int]] = []

    for i in start_indices:
        remaining = sentences[-1].end - sentences[i].start
        if remaining < min_s * 0.8 and duration >= min_s:
            continue
        options: list[tuple[int, float]] = []
        for j in range(i, len(sentences)):
            raw_dur = sentences[j].end - sentences[i].start
            if raw_dur < min_s - 2 * pad:
                continue
            if raw_dur > max_s + 1.0:
                break
            options.append((j, raw_dur))
        if not options:
            if duration < min_seconds:
                raw.append((i, len(sentences) - 1))
            continue
        targets = (min_s, min(35.0, max_s), min(45.0, max_s), max_s)
        picks = {
            min(options, key=lambda item: abs(item[1] - target))[0]
            for target in targets
        }
        raw.extend((i, j) for j in sorted(picks))

    if not raw:
        raw.append((0, len(sentences) - 1))

    candidates: list[Candidate] = []
    seen: set[tuple[float, float]] = set()
    ranked = sorted(
        raw,
        key=lambda pair: (
            0 if round(sentences[pair[0]].start, 3) in preferred else 1,
            pair[0],
            pair[1],
        ),
    )
    for index, (i, j) in enumerate(ranked, start=1):
        window = list(sentences[i : j + 1])
        start, end = snap_to_sentences(
            window[0].start,
            window[-1].end,
            sentences,
            duration=duration,
            pad=pad,
        )
        key = (round(start, 2), round(end, 2))
        if key in seen:
            continue
        if end - start < min_s * 0.8 and duration >= min_s:
            continue
        if end - start > max_s + pad + 0.5:
            continue
        seen.add(key)
        candidates.append(
            Candidate(
                id=f"cand-{index:02d}",
                start=start,
                end=end,
                text=" ".join(
                    part.text.strip() for part in window if part.text.strip()
                ),
                sentences=window,
            )
        )
        if len(candidates) >= max_candidates:
            break
    return candidates


def _start_indices(sentences: Sequence[Segment], preferred: set[float]) -> list[int]:
    indices = {0}
    for index, sentence in enumerate(sentences):
        if round(sentence.start, 3) in preferred or index % 2 == 0:
            indices.add(index)
    return sorted(indices)
