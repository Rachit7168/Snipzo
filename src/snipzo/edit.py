"""Clip editing: trim points, caption text, titles, style, and single-clip re-render."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.models import Clip, ClipMetadata, ClipSet, Project, Render, Word
from snipzo.pick.service import load_clips
from snipzo.projects import get_storage, resolve_project
from snipzo.render.ass import group_words, words_for_clip
from snipzo.render.styles import STYLES, get_style
from snipzo.storage import Storage
from snipzo.transcribe.service import load_transcript

MIN_CLIP_SECONDS = 3.0
MAX_CLIP_SECONDS = 180.0


class CaptionLine(BaseModel):
    """One on-screen caption group with clip-relative times."""

    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = Field(max_length=200)


class ClipEdit(BaseModel):
    """Fields a user can change in the editor; None means unchanged."""

    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    hook_title: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    hashtags: list[str] | None = Field(default=None, max_length=30)
    style_id: str | None = None
    captions: list[CaptionLine] | None = Field(default=None, max_length=400)


class ClipEditorState(BaseModel):
    clip: Clip
    metadata: ClipMetadata | None = None
    captions: list[CaptionLine]
    captions_edited: bool
    styles: list[str]
    source_duration: float


def _edits_name(clip_id: str) -> str:
    return f"edits/{clip_id}.json"


def _find_clip(clipset: ClipSet, clip_id: str) -> Clip:
    for clip in clipset.clips:
        if clip.id == clip_id:
            return clip
    raise SnipzoError(f"Clip not found: {clip_id}")


def default_captions(project: Project, clip: Clip) -> list[CaptionLine]:
    """Caption groups from the transcript (2-4 words each)."""
    words = words_for_clip(load_transcript(project), clip)
    return [
        CaptionLine(
            start=round(group[0].start, 3),
            end=round(group[-1].end, 3),
            text=" ".join(word.text for word in group),
        )
        for group in group_words(words)
    ]


def load_caption_edits(project: Project, clip_id: str) -> list[CaptionLine] | None:
    path = project.root / _edits_name(clip_id)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [CaptionLine.model_validate(item) for item in payload.get("captions", [])]


def load_metadata(project: Project, clip_id: str) -> ClipMetadata | None:
    path = project.renders_dir / f"{clip_id}.json"
    if not path.is_file():
        return None
    return ClipMetadata.model_validate_json(path.read_text(encoding="utf-8"))


def editor_state(ref: str, clip_id: str, settings: Settings) -> ClipEditorState:
    store = get_storage(settings.work_dir)
    project = resolve_project(ref, store)
    clip = _find_clip(load_clips(project), clip_id)
    edits = load_caption_edits(project, clip_id)
    return ClipEditorState(
        clip=clip,
        metadata=load_metadata(project, clip_id),
        captions=edits if edits is not None else default_captions(project, clip),
        captions_edited=edits is not None,
        styles=sorted(STYLES),
        source_duration=project.source.duration,
    )


def captions_to_words(lines: list[CaptionLine]) -> list[Word]:
    """Spread each caption line's words evenly across the line's time span."""
    words: list[Word] = []
    for line in lines:
        tokens = [token for token in re.split(r"\s+", line.text.strip()) if token]
        if not tokens:
            continue
        span = max(0.04 * len(tokens), line.end - line.start)
        step = span / len(tokens)
        for index, token in enumerate(tokens):
            start = line.start + index * step
            words.append(Word(text=token, start=start, end=start + step))
    return words


def apply_clip_edit(
    ref: str,
    clip_id: str,
    edit: ClipEdit,
    settings: Settings,
    *,
    storage: Storage | None = None,
) -> tuple[Clip, bool]:
    """Persist an edit. Returns the updated clip and whether trim points changed."""
    store = storage or get_storage(settings.work_dir)
    project = resolve_project(ref, store)
    clipset = load_clips(project)
    clip = _find_clip(clipset, clip_id)

    start = clip.start if edit.start is None else edit.start
    end = clip.end if edit.end is None else edit.end
    duration = project.source.duration
    if end > duration + 0.05:
        raise SnipzoError(f"End ({end:.2f}s) is past the video end ({duration:.2f}s).")
    end = min(end, duration)
    if end - start < MIN_CLIP_SECONDS:
        raise SnipzoError(f"Clips must be at least {MIN_CLIP_SECONDS:.0f}s long.")
    if end - start > MAX_CLIP_SECONDS:
        raise SnipzoError(f"Clips can be at most {MAX_CLIP_SECONDS:.0f}s long.")
    trimmed = abs(start - clip.start) > 1e-3 or abs(end - clip.end) > 1e-3

    if edit.style_id is not None:
        get_style(edit.style_id)  # validates
    updates: dict[str, object] = {"start": round(start, 3), "end": round(end, 3)}
    if edit.hook_title is not None:
        updates["hook_title"] = edit.hook_title.strip() or None
    if edit.style_id is not None:
        updates["style_id"] = edit.style_id
    updated = clip.model_copy(update=updates)
    clipset = clipset.model_copy(
        update={"clips": [updated if c.id == clip_id else c for c in clipset.clips]}
    )
    store.write_json(project.id, "clips.json", clipset.model_dump(mode="json"))

    meta = load_metadata(project, clip_id)
    if meta is not None:
        meta_updates: dict[str, object] = {}
        if edit.title is not None:
            meta_updates["title"] = edit.title.strip()[:100]
        if edit.description is not None:
            meta_updates["description"] = edit.description
        if edit.hashtags is not None:
            tags = [_hashtag(tag) for tag in edit.hashtags if _hashtag(tag)]
            if "#Shorts" not in tags:
                tags.insert(0, "#Shorts")
            meta_updates["hashtags"] = tags
        if edit.hook_title is not None:
            meta_updates["hook_title"] = updated.hook_title
        if meta_updates:
            meta = meta.model_copy(update=meta_updates)
            store.write_json(
                project.id, f"renders/{clip_id}.json", meta.model_dump(mode="json")
            )
            _rewrite_metadata_index(project, store)

    edits_path = project.root / _edits_name(clip_id)
    if edit.captions is not None and not trimmed:
        lines = [
            line.model_copy(
                update={
                    "start": min(line.start, updated.duration),
                    "end": min(max(line.end, line.start), updated.duration),
                }
            )
            for line in edit.captions
        ]
        store.write_json(
            project.id,
            _edits_name(clip_id),
            {"captions": [line.model_dump(mode="json") for line in lines]},
        )
    elif trimmed and edits_path.is_file():
        # Caption timing is clip-relative; regenerate from the transcript.
        edits_path.unlink()
    return updated, trimmed


def _hashtag(tag: str) -> str:
    cleaned = re.sub(r"[^\w]", "", tag.strip().lstrip("#"))
    return f"#{cleaned}" if cleaned else ""


def _rewrite_metadata_index(project: Project, store: Storage) -> None:
    index_path = project.root / "metadata.json"
    if not index_path.is_file():
        return
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    items = []
    for item in payload.get("items", []):
        meta = load_metadata(project, str(item.get("clip_id")))
        items.append(meta.model_dump(mode="json") if meta else item)
    payload["items"] = items
    store.write_json(project.id, "metadata.json", payload)


def rerender_clip(
    ref: str,
    clip_id: str,
    settings: Settings,
    *,
    storage: Storage | None = None,
    reframe: bool = False,
) -> Render:
    """Re-render one clip with its current trim, captions, title, and style."""
    from snipzo.reframe.detect import get_face_detector
    from snipzo.reframe.service import reframe_clip
    from snipzo.render.service import _crop_or_center, render_clip

    store = storage or get_storage(settings.work_dir)
    project = resolve_project(ref, store)
    if not project.source_path.is_file():
        raise SnipzoError(
            "The source video has been deleted (retention window); "
            "re-upload it to edit this clip."
        )
    clip = _find_clip(load_clips(project), clip_id)
    if reframe:
        reframe_clip(project, clip, store, detector=get_face_detector())
    transcript = load_transcript(project)
    style_id = clip.style_id if clip.style_id in STYLES else settings.caption_style
    edits = load_caption_edits(project, clip_id)
    render = render_clip(
        project,
        clip,
        transcript,
        _crop_or_center(project, clip),
        style=get_style(style_id),
        dest=project.renders_dir / f"{clip_id}.mp4",
        words=captions_to_words(edits) if edits is not None else None,
    )
    renders: list[dict[str, object]] = []
    if (project.root / "renders.json").is_file():
        payload = json.loads((project.root / "renders.json").read_text("utf-8"))
        renders = [
            item
            for item in payload.get("renders", [])
            if item.get("clip_id") != clip_id
        ]
    renders.append(render.model_dump(mode="json"))
    store.write_json(project.id, "renders.json", {"renders": renders})
    return render
