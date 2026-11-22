"""Build word-by-word ASS subtitles with a hook title."""

from __future__ import annotations

import re
from collections.abc import Sequence

from snipzo.models import Clip, Transcript, Word
from snipzo.pick.sentences import words_from_transcript
from snipzo.render.styles import OUTPUT_HEIGHT, OUTPUT_WIDTH, CaptionStyle

_KEYWORD = re.compile(
    r"^(never|always|secret|you|your|why|how|wait|new|free|stop|start|\d+%?)$",
    re.I,
)
_PUNCT = re.compile(r"[^\w]+$", re.UNICODE)


def words_for_clip(transcript: Transcript, clip: Clip) -> list[Word]:
    """Return transcript words that overlap the clip, with clip-relative times."""
    relative: list[Word] = []
    for word in words_from_transcript(transcript):
        if word.end <= clip.start or word.start >= clip.end:
            continue
        start = max(0.0, word.start - clip.start)
        end = max(start + 0.04, min(clip.duration, word.end - clip.start))
        relative.append(
            Word(text=word.text, start=start, end=end, confidence=word.confidence)
        )
    return relative


def hook_title_from_words(clip: Clip, words: Sequence[Word], limit: int = 80) -> str:
    """Use a stored hook title, or the first sentence / first eight words."""
    if clip.hook_title and clip.hook_title.strip():
        return _trim(clip.hook_title.strip(), limit)
    if not words:
        return "Watch this"
    parts: list[str] = []
    for word in words:
        parts.append(word.text)
        token = word.text.strip()
        if token.endswith((".", "!", "?")) or len(parts) >= 8:
            break
    title = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return _trim(title or "Watch this", limit)


def group_words(
    words: Sequence[Word], min_size: int = 2, max_size: int = 4
) -> list[list[Word]]:
    """Pack words into on-screen groups of 2-4."""
    groups: list[list[Word]] = []
    index = 0
    items = list(words)
    while index < len(items):
        remaining = len(items) - index
        size = 3 if min_size <= 3 <= max_size else min_size
        if remaining <= max_size:
            size = remaining
        elif remaining - size == 1:
            # Avoid leaving a single word on screen at the end.
            size = max(min_size, remaining - min_size)
        size = max(min_size, min(max_size, size, remaining))
        groups.append(items[index : index + size])
        index += size
    return [group for group in groups if group]


def build_ass(
    *,
    words: Sequence[Word],
    clip: Clip,
    style: CaptionStyle,
    hook_title: str | None = None,
) -> str:
    """Return an ASS document for one clip."""
    title = hook_title if hook_title is not None else hook_title_from_words(clip, words)
    hook_end = min(clip.duration, max(1.0, style.hook_seconds))
    events = [
        _dialogue(
            0.0,
            hook_end,
            "Hook",
            _ass_text(title.upper()),
        )
    ]
    for group in group_words(words):
        events.extend(_group_events(group, style))
    return _header(style) + "\n".join(events) + "\n"


def ass_time(seconds: float) -> str:
    """Format a timestamp as H:MM:SS.cs (centiseconds)."""
    total = max(0.0, seconds)
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = int(total % 60)
    centis = int(round((total - int(total)) * 100))
    if centis == 100:
        secs += 1
        centis = 0
        if secs == 60:
            secs = 0
            minutes += 1
            if minutes == 60:
                minutes = 0
                hours += 1
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _header(style: CaptionStyle) -> str:
    style_format = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    default = _style_line(
        "Default",
        style,
        size=style.caption_size,
        align=2,
        margin_v=style.caption_margin_v,
        margin_x=70,
    )
    hook = _style_line(
        "Hook",
        style,
        size=style.hook_size,
        align=8,
        margin_v=style.hook_margin_v,
        margin_x=50,
    )
    events_format = (
        "Format: Layer, Start, End, Style, Name, "
        "MarginL, MarginR, MarginV, Effect, Text"
    )
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {OUTPUT_WIDTH}\n"
        f"PlayResY: {OUTPUT_HEIGHT}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        f"{style_format}\n"
        f"{default}\n"
        f"{hook}\n"
        "\n"
        "[Events]\n"
        f"{events_format}\n"
    )


def _style_line(
    name: str,
    style: CaptionStyle,
    *,
    size: int,
    align: int,
    margin_v: int,
    margin_x: int,
) -> str:
    return (
        f"Style: {name},{style.font},{size},{style.primary},&H000000FF,"
        f"{style.outline},&H80000000,-1,0,0,0,100,100,0,0,1,"
        f"{style.outline_width},0,{align},{margin_x},{margin_x},{margin_v},1"
    )


def _group_events(group: Sequence[Word], style: CaptionStyle) -> list[str]:
    events: list[str] = []
    for index, word in enumerate(group):
        text = _group_text(group, index, style)
        end = max(word.end, word.start + 0.04)
        events.append(_dialogue(word.start, end, "Default", text))
    return events


def _group_text(group: Sequence[Word], active: int, style: CaptionStyle) -> str:
    parts: list[str] = []
    for index, word in enumerate(group):
        token = _ass_text(word.text)
        if index == active:
            parts.append(rf"{{\c{style.highlight}&}}{token}{{\c}}")
        elif _is_keyword(word.text):
            parts.append(rf"{{\c{style.highlight}&}}{token}{{\c}}")
        else:
            parts.append(token)
    return r"{\an2}" + " ".join(parts)


def _is_keyword(text: str) -> bool:
    stripped = _PUNCT.sub("", text.strip())
    return bool(_KEYWORD.match(stripped)) or bool(re.search(r"\d", stripped))


def _dialogue(start: float, end: float, style: str, text: str) -> str:
    return f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}"


def _ass_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[: limit - 3].rsplit(" ", 1)[0]
    return (clipped or text[: limit - 3]).rstrip() + "..."
