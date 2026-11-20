"""Select highlight clips for a project and write clips.json."""

from __future__ import annotations

from collections.abc import Sequence

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.models import Clip, ClipSet, Project, ProjectStatus, Segment
from snipzo.pick.candidates import build_candidates
from snipzo.pick.scenes import detect_scene_cuts
from snipzo.pick.scoring import (
    PROMPT_VERSION,
    CandidateScore,
    ClaudeScorer,
    ClipScorer,
    HeuristicScorer,
)
from snipzo.pick.sentences import (
    sentences_from_transcript,
    snap_to_sentences,
    topic_chunks,
)
from snipzo.projects import get_storage, resolve_project
from snipzo.storage import Storage
from snipzo.transcribe.service import load_transcript

DEFAULT_PAD = 0.2
MAX_OVERLAP = 0.4


def get_scorer(settings: Settings) -> ClipScorer:
    """Return Claude when an API key is configured, otherwise the heuristic."""
    if settings.anthropic_api_key:
        return ClaudeScorer(settings.anthropic_api_key, model=settings.anthropic_model)
    return HeuristicScorer()


def pick_clips(
    ref: str,
    settings: Settings,
    *,
    storage: Storage | None = None,
    scorer: ClipScorer | None = None,
    top_n: int | None = None,
    use_scenes: bool = True,
) -> tuple[Project, ClipSet]:
    """Score highlight windows and write `clips.json` for a project."""
    store = storage or get_storage(settings.work_dir)
    project = resolve_project(ref, store)
    transcript = load_transcript(project)
    sentences = sentences_from_transcript(transcript)
    if not sentences:
        raise SnipzoError(
            f"Transcript for project {project.id} has no sentences to clip."
        )

    duration = project.source.duration or transcript.duration
    cuts: list[float] = []
    if use_scenes and project.source_path.is_file():
        try:
            cuts = detect_scene_cuts(project.source_path)
        except SnipzoError:
            cuts = []
    chunks = topic_chunks(sentences, cuts)
    candidates = build_candidates(
        sentences,
        duration=duration,
        min_seconds=settings.clip_min_seconds,
        max_seconds=settings.clip_max_seconds,
        pad=DEFAULT_PAD,
        topic_starts=[chunk.start for chunk in chunks],
    )
    if not candidates:
        raise SnipzoError(
            f"No clip candidates could be built for project {project.id}."
        )

    used_name = "heuristic"
    scores: list[CandidateScore]
    if scorer is not None:
        scores = scorer.score(candidates, transcript)
        used_name = getattr(scorer, "name", "custom")
    elif settings.anthropic_api_key:
        try:
            claude = ClaudeScorer(
                settings.anthropic_api_key, model=settings.anthropic_model
            )
            scores = claude.score(candidates, transcript)
            used_name = claude.name
        except SnipzoError:
            scores = HeuristicScorer().score(candidates, transcript)
            used_name = "heuristic-fallback"
    else:
        scores = HeuristicScorer().score(candidates, transcript)
        used_name = "heuristic"

    count = top_n if top_n is not None else settings.clip_count
    clips = select_top_clips(
        scores,
        sentences,
        duration=duration,
        top_n=count,
        pad=DEFAULT_PAD,
    )
    if not clips:
        raise SnipzoError(f"No clips were selected for project {project.id}.")

    clipset = ClipSet(
        clips=clips,
        prompt_version=PROMPT_VERSION,
        scorer=used_name,
        min_clip_seconds=settings.clip_min_seconds,
        max_clip_seconds=settings.clip_max_seconds,
    )
    store.write_json(project.id, "clips.json", clipset.model_dump(mode="json"))
    updated = project.touch_status(ProjectStatus.PICKED)
    store.save_project(updated)
    return updated, clipset


def load_clips(project: Project) -> ClipSet:
    """Load a previously saved clip set."""
    path = project.clips_path
    if not path.is_file():
        raise SnipzoError(
            f"No clips for project {project.id}; run `snipzo pick` first."
        )
    return ClipSet.model_validate_json(path.read_text(encoding="utf-8"))


def select_top_clips(
    scores: Sequence[CandidateScore],
    sentences: Sequence[Segment],
    *,
    duration: float,
    top_n: int,
    pad: float = DEFAULT_PAD,
    max_overlap: float = MAX_OVERLAP,
) -> list[Clip]:
    """Snap scores to sentence bounds, drop overlaps, and keep the top N."""
    ranked = sorted(scores, key=lambda item: item.score, reverse=True)
    selected: list[Clip] = []
    for item in ranked:
        start, end = snap_to_sentences(
            item.start, item.end, sentences, duration=duration, pad=pad
        )
        if end <= start:
            continue
        if any(
            _overlap(start, end, clip.start, clip.end) > max_overlap
            for clip in selected
        ):
            continue
        index = len(selected) + 1
        selected.append(
            Clip(
                id=f"clip-{index:02d}",
                start=start,
                end=end,
                score=round(item.score, 4),
                reason=item.reason,
                hook_strength=item.hook_strength,
                standalone_clarity=item.standalone_clarity,
                emotion=item.emotion,
                length_score=item.length_score,
            )
        )
        if len(selected) >= top_n:
            break
    return selected


def _overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    overlap = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    shorter = min(end_a - start_a, end_b - start_b)
    if shorter <= 0:
        return 0.0
    return overlap / shorter
