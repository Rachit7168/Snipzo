"""Score highlight candidates with Claude or a deterministic heuristic."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from snipzo.errors import SnipzoError
from snipzo.models import Transcript
from snipzo.pick.candidates import Candidate

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "v1_highlight_selection.txt"
HOOK_WEIGHT = 0.4
CLARITY_WEIGHT = 0.25
EMOTION_WEIGHT = 0.2
LENGTH_WEIGHT = 0.15

_HOOK_PHRASES = (
    "what if",
    "here's",
    "here is",
    "the secret",
    "the truth",
    "let me tell you",
    "you need to",
    "i realized",
    "nobody talks",
    "most people",
    "the problem",
    "guess what",
    "watch this",
    "this is why",
)
_EMOTION_WORDS = (
    "amazing",
    "insane",
    "crazy",
    "love",
    "hate",
    "secret",
    "shocking",
    "unbelievable",
    "terrified",
    "excited",
    "never",
    "always",
    "wow",
    "wait",
    "danger",
    "beautiful",
    "horrible",
    "funny",
    "laugh",
    "cry",
    "win",
    "lose",
)
_WEAK_STARTS = ("and ", "but then", "so then", "or ", "which ", "that ", "because ")


@runtime_checkable
class ClipScorer(Protocol):
    """Assign hook/clarity/emotion/length scores to candidates."""

    name: str

    def score(
        self, candidates: Sequence[Candidate], transcript: Transcript
    ) -> list[CandidateScore]:
        """Return a score for each candidate."""
        ...


class CandidateScore:
    def __init__(
        self,
        candidate_id: str,
        start: float,
        end: float,
        score: float,
        reason: str,
        hook_strength: float,
        standalone_clarity: float,
        emotion: float,
        length_score: float,
    ) -> None:
        self.candidate_id = candidate_id
        self.start = start
        self.end = end
        self.score = score
        self.reason = reason
        self.hook_strength = hook_strength
        self.standalone_clarity = standalone_clarity
        self.emotion = emotion
        self.length_score = length_score


def load_prompt() -> str:
    """Return the versioned highlight-selection prompt."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def combine_score(hook: float, clarity: float, emotion: float, length: float) -> float:
    """Weighted virality score used by both scorers."""
    return round(
        HOOK_WEIGHT * hook
        + CLARITY_WEIGHT * clarity
        + EMOTION_WEIGHT * emotion
        + LENGTH_WEIGHT * length,
        4,
    )


class HeuristicScorer:
    """Deterministic scorer used when no Anthropic API key is set."""

    name = "heuristic"

    def score(
        self, candidates: Sequence[Candidate], transcript: Transcript
    ) -> list[CandidateScore]:
        del transcript
        return [_heuristic(candidate) for candidate in candidates]


class ClaudeScorer:
    """Score candidates with the Anthropic Messages API."""

    name = "claude"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        timeout: float = 90.0,
    ) -> None:
        if not api_key:
            raise SnipzoError("Claude scoring requires SNIPZO_ANTHROPIC_API_KEY.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def score(
        self, candidates: Sequence[Candidate], transcript: Transcript
    ) -> list[CandidateScore]:
        if not candidates:
            return []
        try:
            payload = _claude_request(
                api_key=self.api_key,
                model=self.model,
                timeout=self.timeout,
                user_message=_user_message(candidates, transcript),
            )
            return parse_claude_scores(payload, candidates)
        except (
            SnipzoError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise SnipzoError(f"Claude clip scoring failed: {exc}") from exc


def parse_claude_scores(
    payload: dict[str, object], candidates: Sequence[Candidate]
) -> list[CandidateScore]:
    """Parse a Claude Messages response or a bare `{clips: [...]}` object."""
    text = _content_text(payload)
    data = _extract_json(text) if text else payload
    raw_clips = data.get("clips") if isinstance(data, dict) else None
    if not isinstance(raw_clips, list):
        raise SnipzoError("Claude response did not include a clips array.")
    by_id = {candidate.id: candidate for candidate in candidates}
    scores: list[CandidateScore] = []
    for item in raw_clips:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("id") or "")
        candidate = by_id.get(candidate_id)
        default_start = candidate.start if candidate else 0.0
        default_end = candidate.end if candidate else 0.0
        start_raw = item.get("start")
        end_raw = item.get("end")
        start = float(start_raw if start_raw is not None else default_start)
        end = float(end_raw if end_raw is not None else default_end)
        hook = _clamp(item.get("hook_strength"), 0.5)
        clarity = _clamp(item.get("standalone_clarity"), 0.5)
        emotion = _clamp(item.get("emotion"), 0.5)
        length = _clamp(item.get("length_score"), 0.5)
        score = _clamp(item.get("score"), combine_score(hook, clarity, emotion, length))
        reason = str(item.get("reason") or "Scored by Claude.").strip()
        scores.append(
            CandidateScore(
                candidate_id=candidate_id or (candidate.id if candidate else "cand"),
                start=start,
                end=end,
                score=score,
                reason=reason,
                hook_strength=hook,
                standalone_clarity=clarity,
                emotion=emotion,
                length_score=length,
            )
        )
    if not scores:
        raise SnipzoError("Claude did not return any scored clips.")
    return scores


def _heuristic(candidate: Candidate) -> CandidateScore:
    text = candidate.text.strip()
    lowered = text.lower()
    first = text.split(".", 1)[0][:180]
    hook = 0.25
    if first.endswith("?") or "?" in first[:120]:
        hook += 0.35
    if any(phrase in lowered[:160] for phrase in _HOOK_PHRASES):
        hook += 0.25
    if re.match(r"^(i |you |we |this |that |here )", lowered):
        hook += 0.1
    if re.search(r"\d", first):
        hook += 0.05
    hook = min(1.0, hook)

    clarity = 0.7
    if lowered.startswith(_WEAK_STARTS):
        clarity -= 0.3
    if not text.endswith((".", "!", "?")):
        clarity -= 0.15
    sentence_count = max(1, len(re.findall(r"[.!?]", text)))
    if sentence_count == 1 and candidate.duration > 25:
        clarity -= 0.1
    if sentence_count >= 2:
        clarity += 0.1
    clarity = _clamp(clarity, 0.4)

    emotion = 0.2 + 0.15 * min(3, lowered.count("!"))
    if any(word in lowered for word in _EMOTION_WORDS):
        emotion += 0.3
    if "?" in text:
        emotion += 0.1
    emotion = min(1.0, emotion)

    length = _length_score(candidate.duration)
    score = combine_score(hook, clarity, emotion, length)
    reason = _reason(hook, clarity, emotion, length, first)
    return CandidateScore(
        candidate_id=candidate.id,
        start=candidate.start,
        end=candidate.end,
        score=score,
        reason=reason,
        hook_strength=round(hook, 3),
        standalone_clarity=round(clarity, 3),
        emotion=round(emotion, 3),
        length_score=round(length, 3),
    )


def _length_score(duration: float) -> float:
    # Peak at 35s, zero-ish below 15s or well above 60s.
    if duration <= 0:
        return 0.0
    target = 35.0
    distance = abs(duration - target)
    if 20 <= duration <= 60:
        return _clamp(1.0 - distance / 40.0, 0.4)
    if duration < 20:
        return _clamp(duration / 20.0 * 0.6, 0.1)
    return _clamp(0.6 - (duration - 60) / 40.0, 0.1)


def _reason(
    hook: float, clarity: float, emotion: float, length: float, first: str
) -> str:
    tags: list[str] = []
    if hook >= 0.6:
        tags.append("strong opening hook")
    if clarity >= 0.6:
        tags.append("stands alone")
    if emotion >= 0.5:
        tags.append("emotional energy")
    if length >= 0.7:
        tags.append("good Shorts length")
    if not tags:
        tags.append("usable but not a standout hook")
    preview = first.strip().removesuffix(".")
    if len(preview) > 90:
        preview = preview[:87] + "..."
    return f"{', '.join(tags).capitalize()}. Opens with: {preview}"


def _user_message(candidates: Sequence[Candidate], transcript: Transcript) -> str:
    payload = {
        "language": transcript.language,
        "duration": transcript.duration,
        "candidates": [
            {
                "id": candidate.id,
                "start": candidate.start,
                "end": candidate.end,
                "duration": round(candidate.duration, 2),
                "text": candidate.text,
            }
            for candidate in candidates
        ],
    }
    return (
        "Score these sentence-aligned candidates for YouTube Shorts.\n\n"
        + json.dumps(payload, indent=2)
    )


def _claude_request(
    *, api_key: str, model: str, timeout: float, user_message: str
) -> dict[str, object]:
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 4096,
            "system": load_prompt(),
            "messages": [{"role": "user", "content": user_message}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise SnipzoError(f"Anthropic request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise SnipzoError(f"Anthropic request failed: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise SnipzoError("Anthropic returned an unexpected response.")
    return payload


def _content_text(payload: dict[str, object]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "\n".join(parts).strip()
    if isinstance(payload.get("clips"), list):
        return ""
    return str(payload.get("text") or "").strip()


def _extract_json(text: str) -> dict[str, object]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    else:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            stripped = stripped[start : end + 1]
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise SnipzoError("Claude JSON payload was not an object.")
    return data


def _clamp(value: object, default: float) -> float:
    if value is None:
        return round(min(1.0, max(0.0, default)), 4)
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return round(min(1.0, max(0.0, default)), 4)
    return round(min(1.0, max(0.0, number)), 4)
