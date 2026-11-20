"""Caption and hook style presets for ASS subtitles."""

from __future__ import annotations

from dataclasses import dataclass

from snipzo.errors import SnipzoError

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OUTPUT_FPS = 30


@dataclass(frozen=True)
class CaptionStyle:
    """Visual settings for burned-in captions and the hook title."""

    id: str
    font: str
    caption_size: int
    hook_size: int
    primary: str  # ASS &HAABBGGRR
    highlight: str
    outline: str
    outline_width: int
    caption_margin_v: int
    hook_margin_v: int
    progress_color: str  # ffmpeg color
    hook_seconds: float = 3.0


STYLES: dict[str, CaptionStyle] = {
    "bold-yellow": CaptionStyle(
        id="bold-yellow",
        font="DejaVu Sans",
        caption_size=72,
        hook_size=64,
        primary="&H00FFFFFF",
        highlight="&H0000F5FF",  # yellow
        outline="&H00000000",
        outline_width=6,
        caption_margin_v=280,
        hook_margin_v=90,
        progress_color="0xFFD400",
        hook_seconds=3.0,
    ),
    "clean-white": CaptionStyle(
        id="clean-white",
        font="DejaVu Sans",
        caption_size=64,
        hook_size=56,
        primary="&H00FFFFFF",
        highlight="&H00FFC857",  # soft teal-ish BGR
        outline="&H00202020",
        outline_width=3,
        caption_margin_v=260,
        hook_margin_v=80,
        progress_color="0xFFFFFF",
        hook_seconds=2.5,
    ),
}

DEFAULT_STYLE = "bold-yellow"


def get_style(style_id: str | None) -> CaptionStyle:
    """Return a named caption preset."""
    key = (style_id or DEFAULT_STYLE).strip().lower()
    if key in {"default", ""}:
        key = DEFAULT_STYLE
    if key not in STYLES:
        known = ", ".join(sorted(STYLES))
        raise SnipzoError(
            f"Unknown caption style {style_id!r}. Choose one of: {known}."
        )
    return STYLES[key]
