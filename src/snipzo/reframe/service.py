"""Compute a 9:16 crop path for each selected clip."""

from __future__ import annotations

from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.models import CropPath, Project, ProjectStatus
from snipzo.pick.service import load_clips
from snipzo.projects import get_storage, resolve_project
from snipzo.reframe.detect import FaceBox, FaceDetector, get_face_detector
from snipzo.reframe.track import build_crop_path, detect_clip_faces
from snipzo.storage import Storage


def reframe_project(
    ref: str,
    settings: Settings,
    *,
    storage: Storage | None = None,
    detector: FaceDetector | None | bool = True,
    sample_fps: float = 5.0,
) -> tuple[Project, list[CropPath]]:
    """Write a crop path JSON file for each clip in the project."""
    store = storage or get_storage(settings.work_dir)
    project = resolve_project(ref, store)
    clipset = load_clips(project)
    if not clipset.clips:
        raise SnipzoError(f"Project {project.id} has no clips to reframe.")

    active_detector: FaceDetector | None
    if detector is True:
        active_detector = get_face_detector()
    elif detector is False:
        active_detector = None
    else:
        active_detector = detector

    width = project.source.width
    height = project.source.height
    paths: list[CropPath] = []
    for clip in clipset.clips:
        detections: list[tuple[float, FaceBox | None]] = []
        if active_detector is not None and project.source_path.is_file():
            detections = detect_clip_faces(
                str(project.source_path),
                clip,
                active_detector,
                fps=sample_fps,
            )
        path = build_crop_path(
            clip,
            width=width,
            height=height,
            detections=detections,
        )
        store.write_json(
            project.id,
            f"crops/{clip.id}.json",
            path.model_dump(mode="json"),
        )
        paths.append(path)

    store.write_json(
        project.id,
        "crops.json",
        {"clips": [path.model_dump(mode="json") for path in paths]},
    )
    updated = project.touch_status(ProjectStatus.REFRAMED)
    store.save_project(updated)
    return updated, paths


def load_crop_path(project: Project, clip_id: str) -> CropPath:
    """Load a saved crop path for one clip."""
    path = project.crops_dir / f"{clip_id}.json"
    if not path.is_file():
        raise SnipzoError(
            f"No crop path for {clip_id} in project {project.id}; "
            "run `snipzo reframe` first."
        )
    return CropPath.model_validate_json(path.read_text(encoding="utf-8"))
