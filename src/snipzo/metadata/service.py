"""Generate and persist metadata for every clip in a project."""

from __future__ import annotations

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


def get_generator(settings: Settings) -> MetadataGenerator:
    """Return Claude when an API key is configured, otherwise the heuristic."""
    if settings.anthropic_api_key:
        return ClaudeMetadataGenerator(
            settings.anthropic_api_key, model=settings.anthropic_model
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
        except SnipzoError:
            if generator is not None:
                raise
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
