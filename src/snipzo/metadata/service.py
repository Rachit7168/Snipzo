"""Generate and persist metadata for every clip in a project."""

from __future__ import annotations

import logging

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.metadata.generate import (
    PROMPT_VERSION,
    ClaudeMetadataGenerator,
    HeuristicMetadataGenerator,
    MetadataGenerator,
)
from snipzo.models import ClipMetadata, ClipSet, Project
from snipzo.pick.service import load_clips
from snipzo.projects import get_storage, resolve_project
from snipzo.storage import Storage
from snipzo.transcribe.service import load_transcript

log = logging.getLogger(__name__)


def get_generator(settings: Settings) -> MetadataGenerator:
    """Return Claude when an API key is configured, otherwise the heuristic.

    Raises ``SnipzoError`` when ``settings.require_llm_metadata`` is enabled
    and ``settings.anthropic_api_key`` is missing.
    """
    api_key = (settings.anthropic_api_key or "").strip()
    if api_key:
        return ClaudeMetadataGenerator(api_key, model=settings.anthropic_model)
    if settings.require_llm_metadata:
        raise SnipzoError(
            "LLM metadata is required (SNIPZO_REQUIRE_LLM_METADATA=true) "
            "but SNIPZO_ANTHROPIC_API_KEY is not set."
        )
    log.warning(
        "SNIPZO_ANTHROPIC_API_KEY is not set; using heuristic metadata generator."
    )
    return HeuristicMetadataGenerator()


def generate_metadata(
    ref: str,
    settings: Settings,
    *,
    storage: Storage | None = None,
    generator: MetadataGenerator | None = None,
) -> tuple[Project, list[ClipMetadata]]:
    """Write metadata JSON for each clip and update hook titles on clips.json."""
    store = storage or get_storage(settings.work_dir)
    project = resolve_project(ref, store)
    clipset = load_clips(project)
    if not clipset.clips:
        raise SnipzoError(f"Project {project.id} has no clips for metadata.")
    transcript = load_transcript(project)

    used = generator or get_generator(settings)

    results: list[ClipMetadata] = []
    updated_clips = []
    for clip in clipset.clips:
        try:
            meta = used.generate(clip, transcript, project.language)
        except SnipzoError as exc:
            if generator is not None or settings.require_llm_metadata:
                raise
            log.warning(
                "Claude metadata failed for %s (%s); falling back to heuristic.",
                clip.id,
                exc,
            )
            meta = HeuristicMetadataGenerator().generate(
                clip, transcript, project.language
            )
            meta = meta.model_copy(update={"generator": "heuristic-fallback"})
        dest_name = f"renders/{clip.id}.json"
        store.write_json(project.id, dest_name, meta.model_dump(mode="json"))
        updated_clips.append(clip.model_copy(update={"hook_title": meta.hook_title}))
        results.append(meta)

    store.write_json(
        project.id,
        "clips.json",
        ClipSet(
            clips=updated_clips,
            prompt_version=clipset.prompt_version,
            scorer=clipset.scorer,
            min_clip_seconds=clipset.min_clip_seconds,
            max_clip_seconds=clipset.max_clip_seconds,
        ).model_dump(mode="json"),
    )
    store.write_json(
        project.id,
        "metadata.json",
        {
            "prompt_version": PROMPT_VERSION,
            "items": [item.model_dump(mode="json") for item in results],
        },
    )
    return project, results
