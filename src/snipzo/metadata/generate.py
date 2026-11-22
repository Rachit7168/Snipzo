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
from snipzo.render.ass import words_for_clip

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "v1_metadata.txt"
TITLE_LIMIT = 100
HOOK_LIMIT = 80
STOPWORDS = frozenset(
    """
    a an the and or but if to of in on for with at from by is are was were be been
    being have has had do does did this that these those it its you your we our they
    their i me my he him his she her as so just not about into over after before
    then than too very can will would should could may might must shall what when
    where which who whom whose why how all any both each few more most other some
    such no nor only own same up down out off here there also still even much many
    within without through while during since until
    """.split()
)
FILLER_WORDS = frozenset(
    """
    like know yeah yes okay ok uh um er ah hm hmm oh well right basically actually
    literally honestly really probably maybe kind sort stuff thing things something
    anything everything nothing lot lots want wants wanted said say says saying
    think thought mean means see saw look looks hear heard go goes going gone come
    comes coming came get got gotten make makes made take takes took feel feels felt
    try tries tried tell tells told ask asks asked talk talking because coz cuz
    gonna wanna gotta thats theres heres youre im ive ill dont didnt doesnt wont
    cant isnt arent were theyre its hes shes whats whos lets ever never always
    again back today tomorrow day end way time part bit one ones able hard long
    good great big new old first last next early late whole obviously definitely
    totally pretty quite aspects hit put keep kept let seem seems
    """.split()
)
NON_HASHTAG_WORDS = STOPWORDS | FILLER_WORDS
_TITLE_MINOR_WORDS = frozenset(
    "a an the and or but nor for of in on to at by from with as".split()
)
_DANGLING_END_WORDS = frozenset(
    """
    a an the and or but so because if to of in on for with at from by is are was
    were be my your our their his her it this that you we they i
    """.split()
)
_IDIOM_PATTERNS = (
    re.compile(r"\bat the end of the day\b[,\s]*", re.I),
    re.compile(r"\bto be honest\b[,\s]*", re.I),
    re.compile(r"\band stuff like (?:this|that)\b[,\s]*", re.I),
    re.compile(r"\bstuff like (?:this|that)\b[,\s]*", re.I),
    re.compile(r"\byou know\b[,\s]*", re.I),
    re.compile(r"(?:^|,\s*)\bi mean\b[,\s]*", re.I),
    re.compile(r"\bkind of\b[,\s]*", re.I),
    re.compile(r"\bsort of\b[,\s]*", re.I),
    re.compile(r"\bmore like\b[,\s]*", re.I),
    re.compile(r"(?:^|,\s*)\byou see\b[,\s]+", re.I),
    re.compile(r"\blike i said\b[,\s]*", re.I),
    re.compile(r"\bas i said\b[,\s]*", re.I),
)
_LEADING_FILLER_RE = re.compile(
    r"^(?:so|and|but|well|yeah|yes|okay|ok|uh|um|er|ah|like|right|"
    r"basically|actually|literally|honestly|then|just)\b[,\s]*",
    re.I,
)
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9']*")


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
    """Deterministic keyphrase metadata used when no Anthropic API key is set."""

    name = "heuristic"

    def generate(
        self, clip: Clip, transcript: Transcript, language: str | None
    ) -> ClipMetadata:
        del language
        words = words_for_clip(transcript, clip)
        text = " ".join(word.text for word in words).strip()
        keyphrases = extract_keyphrases(text)
        title = _trim(_select_title(text, keyphrases), TITLE_LIMIT)
        hook = _trim(_select_hook(title, keyphrases), HOOK_LIMIT)
        hashtags = build_hashtags(keyphrases)
        tags = _normalize_tags([kp for kp, _score in keyphrases], hashtags)
        cleaned_sentences = [
            _clean_sentence(sentence) for sentence in _sentences(text)
        ]
        good_sentences = [s for s in cleaned_sentences if len(s.split()) >= 4]
        body = " ".join(good_sentences[:2]) or title
        description = (
            f"{body}\n\n"
            "Follow for more highlights from the full conversation.\n\n"
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


def clean_spoken_text(text: str) -> str:
    """Strip conversational filler idioms and repeated stutter words."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    for pat in _IDIOM_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    cleaned = re.sub(r",\s*like\s*,", ", ", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\b(i|we|you|they|it|that|was|is|are|said|and|so|but|then|yeah)\s+"
        r"like\b[,\s]*",
        r"\1 ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\b([A-Za-z']+)\s*,\s*\1\b", r"\1", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" ,")


def extract_keyphrases(text: str) -> list[tuple[str, float]]:
    """Extract ranked stopword- and filler-filtered unigram/bigram keyphrases."""
    cleaned = clean_spoken_text(text)
    clauses = re.split(r"[.!?,;:]+", cleaned)
    scores: dict[str, float] = {}
    display: dict[str, str] = {}

    for clause in clauses:
        raw_tokens = _TOKEN.findall(clause)
        content_seq: list[tuple[str, str, bool]] = []
        for idx, tok in enumerate(raw_tokens):
            norm = tok.lower().replace("'", "")
            is_acro = tok.isupper() and len(tok) >= 2
            is_proper = (idx > 0 and tok[:1].isupper() and len(tok) >= 3) or is_acro
            if (
                norm in NON_HASHTAG_WORDS
                or (len(norm) < 3 and not is_acro)
                or "'" in tok
            ):
                content_seq.append(("", "", False))
                continue
            disp = tok if is_proper else norm
            content_seq.append((norm, disp, is_proper))

        for i, (norm, disp, is_proper) in enumerate(content_seq):
            if not norm:
                continue
            w_score = (
                1.0
                + (0.9 if is_proper else 0.0)
                + (0.35 if len(norm) >= 7 else 0.0)
            )
            scores[norm] = scores.get(norm, 0.0) + w_score
            if norm not in display or is_proper:
                display[norm] = disp

            if i + 1 < len(content_seq) and content_seq[i + 1][0]:
                n2, d2, p2 = content_seq[i + 1]
                phrase_key = f"{norm} {n2}"
                phrase_disp = f"{disp} {d2}"
                p_score = 1.6 + (0.8 if (is_proper or p2) else 0.0)
                scores[phrase_key] = scores.get(phrase_key, 0.0) + p_score
                if phrase_key not in display:
                    display[phrase_key] = phrase_disp

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
    return [(display[k], v) for k, v in ranked]


def build_hashtags(keyphrases: Sequence[tuple[str, float]]) -> list[str]:
    """Build clean PascalCase hashtags from keyphrases, always starting with #Shorts."""
    tags = ["#Shorts"]
    seen = {"shorts"}
    used_words: set[str] = set()
    for phrase, _score in keyphrases:
        parts = phrase.split()
        if len(parts) > 2:
            continue
        norms = [p.lower() for p in parts]
        if any(n in NON_HASHTAG_WORDS for n in norms):
            continue
        if any(n in used_words for n in norms):
            continue
        tag_body = "".join(
            p if p.isupper() else p[:1].upper() + p[1:] for p in parts
        )
        tag_body = re.sub(r"[^A-Za-z0-9]", "", tag_body)
        if len(tag_body) < 3 or tag_body.lower() in seen:
            continue
        seen.add(tag_body.lower())
        used_words.update(norms)
        tags.append(f"#{tag_body}")
        if len(tags) >= 6:
            break
    return tags


def _clean_sentence(sentence: str) -> str:
    cleaned = clean_spoken_text(sentence)
    while True:
        nxt = _LEADING_FILLER_RE.sub("", cleaned).strip(" ,")
        if nxt == cleaned:
            break
        cleaned = nxt
    words = cleaned.split()
    while (
        words
        and words[-1].rstrip(".,!?").lower().replace("'", "") in _DANGLING_END_WORDS
        and not words[-1].endswith((".", "!", "?"))
    ):
        words.pop()
    return " ".join(words).strip(" ,;:-")


def _select_title(text: str, keyphrases: Sequence[tuple[str, float]]) -> str:
    raw_sents = _sentences(text)
    top_terms = {w.lower() for kp, _ in keyphrases[:8] for w in kp.split()}
    candidates: list[tuple[float, str]] = []

    for sent in raw_sents:
        cs = _clean_sentence(sent)
        if not cs:
            continue
        sub_clauses = [cs]
        if len(cs.split()) > 9 and re.search(r"\s+and\s+", cs, re.I):
            parts = re.split(r"\s+and\s+", cs, maxsplit=1, flags=re.I)
            first_half = parts[0].strip(" ,")
            second_half = parts[1].strip(" ,") if len(parts) > 1 else ""
            if len(first_half.split()) >= 5:
                sub_clauses.append(first_half)
                if re.match(r"^(?:you|i|we|they|then|yeah|so)\b", second_half, re.I):
                    # Prefer crisp opening clause over conversational tail.
                    sub_clauses = [first_half]

        for cand in sub_clauses:
            words = cand.split()
            if len(words) < 4:
                continue
            norms = [w.lower().strip(".,!?\"'") for w in words]
            content_hits = [
                n
                for n in norms
                if n.replace("'", "") not in NON_HASHTAG_WORDS and len(n) >= 3
            ]
            if len(content_hits) < 2:
                continue
            kp_hits = sum(1 for n in norms if n in top_terms)
            filler_hits = sum(
                1 for n in norms if n.replace("'", "") in FILLER_WORDS
            )
            score = kp_hits * 2.0 + len(content_hits) * 0.6 - filler_hits * 1.5
            if cand.endswith("?"):
                score += 2.6
                if norms[0] in {"what", "why", "how"}:
                    score += 1.2
            if 5 <= len(words) <= 10:
                score += 1.6
            elif len(words) > 13:
                score -= 1.2
            if (
                norms[0].replace("'", "") in _DANGLING_END_WORDS
                and norms[0] not in {"in", "on", "what", "why", "how"}
            ):
                score -= 1.2
            # Slight preference for crisp sub-clause when full sentence had a tail.
            if cand != cs:
                score += 0.6
            candidates.append((score, cand))

    candidates.sort(key=lambda item: -item[0])
    if candidates and candidates[0][0] >= 3.0:
        best = candidates[0][1].rstrip(".")
        if len(best) > 78:
            best = best[:75].rsplit(" ", 1)[0].rstrip(" ,;:-")
        return _title_case(best)

    return _headline_from_keyphrases(keyphrases)


def _select_hook(title: str, keyphrases: Sequence[tuple[str, float]]) -> str:
    if len(title) <= HOOK_LIMIT:
        return title
    headline = _headline_from_keyphrases(keyphrases)
    return headline if len(headline) <= HOOK_LIMIT else _trim(title, HOOK_LIMIT)


def _headline_from_keyphrases(keyphrases: Sequence[tuple[str, float]]) -> str:
    chunks: list[str] = []
    used_words: set[str] = set()
    for kp, _score in keyphrases:
        parts = kp.split()
        lows = [part.lower() for part in parts]
        if any(low in used_words or low in NON_HASHTAG_WORDS for low in lows):
            continue
        formatted = " ".join(
            part if part.isupper() else part[:1].upper() + part[1:]
            for part in parts
        )
        chunks.append(formatted)
        used_words.update(lows)
        if len(chunks) >= 3:
            break
    if len(chunks) == 3:
        return f"{chunks[0]}, {chunks[1]} & {chunks[2]}"
    if len(chunks) == 2:
        return f"{chunks[0]} & {chunks[1]}"
    if chunks:
        return chunks[0]
    return "Key Highlights"


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


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _title_case(text: str) -> str:
    if text.endswith("?"):
        return text[:1].upper() + text[1:] if text else text
    words = text.split()
    result: list[str] = []
    for index, word in enumerate(words):
        lower = word.lower()
        if lower == "i" or lower.startswith("i'"):
            result.append("I" + word[1:])
        elif word.isupper() and len(word) >= 2:
            result.append(word)
        elif index > 0 and lower in _TITLE_MINOR_WORDS:
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
        if tag.lower() == "#shorts":
            tag = "#Shorts"
        else:
            body = re.sub(r"[^A-Za-z0-9]", "", tag.lstrip("#"))
            if not body or body.lower() in NON_HASHTAG_WORDS or len(body) < 2:
                continue
            tag = "#" + body
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
    for raw in [*extras, *values, "shorts"]:
        for part in raw.split():
            tag = re.sub(r"[^a-z0-9]+", "", part.lower())
            if (
                not tag
                or tag in seen
                or len(tag) < 2
                or (tag != "shorts" and tag in NON_HASHTAG_WORDS)
            ):
                continue
            seen.add(tag)
            tags.append(tag)
            if len(tags) >= 10:
                return tags
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
