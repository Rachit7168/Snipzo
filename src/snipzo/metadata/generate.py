"""Claude and heuristic metadata generators."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from snipzo.errors import SnipzoError
from snipzo.models import Clip, ClipMetadata, Transcript
from snipzo.render.ass import hook_title_from_words, words_for_clip

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "v1_metadata.txt"
TITLE_LIMIT = 100
HOOK_LIMIT = 80
STOPWORDS = frozenset(
    """
    a an the and or but if to of in on for with at from by is are was were be
    this that these those it its you your we they i me my our as so just not
    about into over after before then than too very can will would should
    """.split()
)
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9']+")


@runtime_checkable
class MetadataGenerator(Protocol):
    """Produce title/description/hashtags for a clip."""

    name: str

    def generate(
        self, clip: Clip, transcript: Transcript, language: str | None
    ) -> ClipMetadata:
        """Return metadata for one clip."""
        ...


def load_prompt() -> str:
    """Return the versioned metadata prompt."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def validate_metadata(meta: ClipMetadata) -> ClipMetadata:
    """Enforce title length and guarantee a #Shorts hashtag."""
    title = _trim(meta.title.strip() or "New Short", TITLE_LIMIT)
    hook = _trim((meta.hook_title or title).strip() or title, HOOK_LIMIT)
    hashtags = _normalize_hashtags(meta.hashtags)
    tags = _normalize_tags(meta.tags, hashtags)
    description = (meta.description or title).strip()
    if "#Shorts" not in description and "shorts" not in description.lower():
        description = f"{description}\n\n{' '.join(hashtags)}"
    return meta.model_copy(
        update={
            "title": title,
            "hook_title": hook,
            "description": description.strip(),
            "hashtags": hashtags,
            "tags": tags,
        }
    )


class HeuristicMetadataGenerator:
    """Deterministic metadata used when no Anthropic API key is set."""

    name = "heuristic"

    def generate(
        self, clip: Clip, transcript: Transcript, language: str | None
    ) -> ClipMetadata:
        del language
        words = words_for_clip(transcript, clip)
        hook = hook_title_from_words(clip, words, limit=HOOK_LIMIT)
        title = _trim(_title_case(hook.rstrip(".")), TITLE_LIMIT)
        if not title.endswith(("?", "!")) and len(title) < TITLE_LIMIT - 1:
            # Keep questions; otherwise a period-free hook reads better.
            pass
        text = " ".join(word.text for word in words).strip()
        keywords = _keywords(text)
        hashtags = _normalize_hashtags(["#Shorts", *keywords[:6]])
        tags = _normalize_tags(keywords, hashtags)
        sentences = _sentences(text)
        body = " ".join(sentences[:2]) or title
        description = (
            f"{body}\n\n"
            "If this helped, follow for more short takes from the full video.\n\n"
            + " ".join(hashtags)
        )
        return validate_metadata(
            ClipMetadata(
                clip_id=clip.id,
                title=title,
                hook_title=hook,
                description=description,
                hashtags=hashtags,
                tags=tags,
                generator=self.name,
            )
        )


class ClaudeMetadataGenerator:
    """Generate metadata with the Anthropic Messages API."""

    name = "claude"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        timeout: float = 90.0,
    ) -> None:
        if not api_key:
            raise SnipzoError("Claude metadata requires SNIPZO_ANTHROPIC_API_KEY.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(
        self, clip: Clip, transcript: Transcript, language: str | None
    ) -> ClipMetadata:
        words = words_for_clip(transcript, clip)
        text = " ".join(word.text for word in words).strip()
        payload = _claude_request(
            api_key=self.api_key,
            model=self.model,
            timeout=self.timeout,
            user_message=_user_message(clip, text, language),
        )
        parsed = parse_claude_metadata(payload, clip.id)
        parsed = parsed.model_copy(update={"generator": self.name})
        return validate_metadata(parsed)


def parse_claude_metadata(payload: dict[str, object], clip_id: str) -> ClipMetadata:
    """Parse a Claude Messages response or a bare metadata object."""
    text = _content_text(payload)
    data = _extract_json(text) if text else payload
    if not isinstance(data, dict):
        raise SnipzoError("Claude metadata payload was not an object.")
    return ClipMetadata(
        clip_id=clip_id,
        title=str(data.get("title") or "New Short"),
        hook_title=str(data.get("hook_title") or data.get("title") or "New Short"),
        description=str(data.get("description") or ""),
        hashtags=_string_list(data.get("hashtags")),
        tags=_string_list(data.get("tags")),
        generator="claude",
    )


def _user_message(clip: Clip, text: str, language: str | None) -> str:
    payload = {
        "clip_id": clip.id,
        "start": clip.start,
        "end": clip.end,
        "duration": round(clip.duration, 2),
        "language": language or "en",
        "reason": clip.reason,
        "transcript": text,
    }
    return "Write Shorts metadata for this clip.\n\n" + json.dumps(payload, indent=2)


def _claude_request(
    *, api_key: str, model: str, timeout: float, user_message: str
) -> dict[str, object]:
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 1024,
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


def _keywords(text: str) -> list[str]:
    counts: dict[str, int] = {}
    for raw in _TOKEN.findall(text):
        word = raw.lower().strip("'")
        if word in STOPWORDS or len(word) < 3:
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _count in ranked]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _title_case(text: str) -> str:
    if text.endswith("?"):
        return text[0].upper() + text[1:] if text else text
    words = text.split()
    result: list[str] = []
    for index, word in enumerate(words):
        lower = word.lower()
        if index > 0 and lower in STOPWORDS:
            result.append(lower)
        else:
            result.append(word[:1].upper() + word[1:] if word else word)
    return " ".join(result)


def _normalize_hashtags(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    for raw in values:
        tag = raw.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        # Keep #Shorts canonical even if the model used #shorts.
        if tag.lower() == "#shorts":
            tag = "#Shorts"
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(tag)
    if "#shorts" not in seen:
        tags.insert(0, "#Shorts")
    return tags[:8]


def _normalize_tags(values: Sequence[str], hashtags: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    extras = [item.lstrip("#") for item in hashtags]
    for raw in [*values, *extras, "shorts"]:
        tag = re.sub(r"[^a-z0-9]+", "", raw.lower())
        if not tag or tag in seen or len(tag) < 2:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags[:10]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[: limit - 3].rsplit(" ", 1)[0]
    return (clipped or text[: limit - 3]).rstrip(" ,;:-") + "..."
