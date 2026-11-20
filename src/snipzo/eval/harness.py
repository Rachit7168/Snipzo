"""CSV ratings template and summary for human clip evaluations."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.models import ClipMetadata, Project
from snipzo.pick.service import load_clips

RATING_FIELDS = (
    "video",
    "project_id",
    "clip_id",
    "start",
    "end",
    "score",
    "reason",
    "title",
    "render_path",
    "usable",
    "rating",
    "notes",
)

_YES = frozenset({"yes", "y", "true", "1", "usable"})


def write_ratings_template(
    dest: Path,
    rows: Sequence[dict[str, object]],
    *,
    append: bool = False,
) -> Path:
    """Write or append clip rows with empty human-rating columns."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, str]] = []
    if append and dest.is_file():
        with dest.open(encoding="utf-8", newline="") as handle:
            existing = list(csv.DictReader(handle))
    seen = {(row.get("project_id"), row.get("clip_id")) for row in existing}
    merged = list(existing)
    for row in rows:
        key = (str(row.get("project_id", "")), str(row.get("clip_id", "")))
        if key in seen:
            continue
        merged.append({field: str(row.get(field, "")) for field in RATING_FIELDS})
        seen.add(key)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(RATING_FIELDS))
        writer.writeheader()
        writer.writerows(merged)
    return dest


def ratings_rows_for_project(
    project: Project, *, video: Path | None = None
) -> list[dict[str, object]]:
    """Build template rows for every clip in a finished project."""
    clipset = load_clips(project)
    metadata_by_id = _load_metadata_index(project)
    rows: list[dict[str, object]] = []
    source = str(video or project.source.path)
    for clip in clipset.clips:
        meta = metadata_by_id.get(clip.id)
        render = project.renders_dir / f"{clip.id}.mp4"
        rows.append(
            {
                "video": source,
                "project_id": project.id,
                "clip_id": clip.id,
                "start": f"{clip.start:.3f}",
                "end": f"{clip.end:.3f}",
                "score": f"{clip.score:.4f}",
                "reason": clip.reason,
                "title": meta.title if meta else (clip.hook_title or ""),
                "render_path": str(render) if render.is_file() else "",
                "usable": "",
                "rating": "",
                "notes": "",
            }
        )
    return rows


def eval_summary(ratings_csv: Path) -> dict[str, float | int]:
    """Compute how many rated clips were marked usable without edits."""
    if not ratings_csv.is_file():
        raise SnipzoError(f"Ratings CSV not found: {ratings_csv}")
    with ratings_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"clips": 0, "rated": 0, "usable": 0, "usable_percent": 0.0}
    rated = [row for row in rows if (row.get("usable") or "").strip()]
    usable = [row for row in rated if (row.get("usable") or "").strip().lower() in _YES]
    percent = (100.0 * len(usable) / len(rated)) if rated else 0.0
    return {
        "clips": len(rows),
        "rated": len(rated),
        "usable": len(usable),
        "usable_percent": round(percent, 1),
    }


def _load_metadata_index(project: Project) -> dict[str, ClipMetadata]:
    index: dict[str, ClipMetadata] = {}
    manifest = project.root / "metadata.json"
    if manifest.is_file():
        import json

        payload = json.loads(manifest.read_text(encoding="utf-8"))
        for item in payload.get("items") or []:
            meta = ClipMetadata.model_validate(item)
            index[meta.clip_id] = meta
        return index
    if project.renders_dir.is_dir():
        for path in project.renders_dir.glob("*.json"):
            meta = ClipMetadata.model_validate_json(path.read_text(encoding="utf-8"))
            index[meta.clip_id] = meta
    return index


VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def collect_videos(source: Path) -> list[Path]:
    """Load a single video, a directory of videos, or a text file of paths."""
    source = source.expanduser()
    if source.is_dir():
        videos = [
            path
            for path in sorted(source.iterdir())
            if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
        ]
        if not videos:
            raise SnipzoError(f"No video files found in {source}.")
        return videos
    if not source.is_file():
        raise SnipzoError(f"Video list or file not found: {source}")
    if source.suffix.lower() in VIDEO_SUFFIXES:
        return [source]
    paths: list[Path] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        path = Path(item).expanduser()
        if not path.is_file():
            raise SnipzoError(f"Video not found: {path}")
        paths.append(path)
    if not paths:
        raise SnipzoError(f"No video paths listed in {source}.")
    return paths


def run_eval_set(
    source: Path,
    settings: Settings,
    out_dir: Path,
    *,
    top_n: int | None = None,
    style_id: str | None = None,
    force: bool = False,
    on_progress: object | None = None,
) -> tuple[list[Project], Path]:
    """Run the pipeline on a test set and write a ratings CSV for human review."""
    from snipzo.pipeline import run_pipeline

    videos = collect_videos(source)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "ratings.csv"
    projects: list[Project] = []
    for video in videos:
        project = run_pipeline(
            video,
            settings,
            top_n=top_n,
            style_id=style_id,
            force=force,
            on_progress=on_progress if callable(on_progress) else None,
        )
        rows = ratings_rows_for_project(project, video=video)
        write_ratings_template(csv_path, rows, append=True)
        projects.append(project)
    return projects, csv_path

