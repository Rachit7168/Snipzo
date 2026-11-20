from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from snipzo.cli import app
from snipzo.config import Settings
from snipzo.models import (
    Clip,
    ClipSet,
    Project,
    ProjectStatus,
    VideoInfo,
)
from snipzo.reframe.detect import FaceBox
from snipzo.reframe.geometry import (
    center_origin,
    crop_size,
    origin_from_point,
    smooth_series,
)
from snipzo.reframe.service import reframe_project
from snipzo.reframe.track import build_crop_path
from snipzo.storage import LocalStorage


def test_center_crop_for_16x9() -> None:
    crop_w, crop_h = crop_size(1280, 720)
    assert crop_h == 720
    assert crop_w % 2 == 0
    assert abs(crop_w / crop_h - 9 / 16) < 0.02
    x, y = center_origin(1280, 720, crop_w, crop_h)
    assert y == 0
    assert x == (1280 - crop_w) / 2


def test_crop_stays_inside_frame() -> None:
    crop_w, crop_h = crop_size(1280, 720)
    x, y = origin_from_point(0, 0, 1280, 720, crop_w, crop_h)
    assert x == 0
    assert y == 0
    x, y = origin_from_point(1280, 720, 1280, 720, crop_w, crop_h)
    assert x == 1280 - crop_w
    assert y == 720 - crop_h


def test_smooth_series_reduces_jitter() -> None:
    raw = [0.0, 100.0, 0.0, 100.0, 0.0, 100.0]
    smoothed = smooth_series(raw, alpha=0.3)
    # Peak-to-peak should shrink after exponential smoothing.
    assert max(smoothed) - min(smoothed) < max(raw) - min(raw)


def _clip() -> Clip:
    return Clip(
        id="clip-01",
        start=0.0,
        end=2.0,
        score=0.8,
        reason="test",
    )


def test_build_crop_path_center_without_detections() -> None:
    path = build_crop_path(_clip(), width=1280, height=720, detections=[])
    assert path.mode == "center"
    assert path.keyframes[0].x == center_origin(1280, 720, *crop_size(1280, 720))[0]


def test_build_crop_path_blur_when_no_face() -> None:
    detections = [(0.0, None), (0.5, None), (1.0, None)]
    path = build_crop_path(_clip(), width=1280, height=720, detections=detections)
    assert path.mode == "blur"
    assert all(frame.x == path.keyframes[0].x for frame in path.keyframes)


def test_build_crop_path_follows_face_and_smooths() -> None:
    crop_w, crop_h = crop_size(1280, 720)
    # Alternate a face near the left and right edges.
    left = FaceBox(x=20, y=100, w=80, h=80)
    right = FaceBox(x=1100, y=100, w=80, h=80)
    detections = [
        (0.0, left),
        (0.2, right),
        (0.4, left),
        (0.6, right),
    ]
    path = build_crop_path(
        _clip(), width=1280, height=720, detections=detections, smooth_alpha=0.3
    )
    assert path.mode == "face"
    raw_xs = [
        origin_from_point(face.cx, face.cy, 1280, 720, crop_w, crop_h)[0]
        for _, face in detections
        if face is not None
    ]
    smooth_xs = [key.x for key in path.keyframes]
    assert max(smooth_xs) - min(smooth_xs) < max(raw_xs) - min(raw_xs)
    assert all(0 <= key.x <= 1280 - key.w for key in path.keyframes)


class FixedFaceDetector:
    name = "fixed"

    def detect(self, frame: object) -> list[FaceBox]:
        del frame
        return [FaceBox(x=400, y=120, w=120, h=120, score=0.99)]


def _project_with_clip(tmp_path: Path, video: Path) -> tuple[Project, Settings]:
    settings = Settings(work_dir=tmp_path / "data", _env_file=None)
    storage = LocalStorage(settings.work_dir)
    project = Project(
        id="face1",
        status=ProjectStatus.PICKED,
        work_dir=settings.work_dir,
        source=VideoInfo(
            path=video,
            duration=2.0,
            width=320,
            height=180,
            fps=30,
            has_audio=True,
            codec="h264",
        ),
    )
    # Copy the sample into the project dir so source_path resolves.
    stored = storage.copy_into(project.id, video, video.name)
    project = project.model_copy(
        update={"source": project.source.model_copy(update={"path": stored})}
    )
    storage.save_project(project)
    storage.write_json(
        project.id,
        "clips.json",
        ClipSet(clips=[_clip()], scorer="test").model_dump(mode="json"),
    )
    return project, settings


def test_reframe_project_with_mock_detector(
    sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, settings = _project_with_clip(tmp_path, sample_video)

    def fake_detect(video_path: str, clip: Clip, detector: object, fps: float = 5.0):
        del video_path, clip, detector, fps
        face = FaceBox(x=80, y=40, w=60, h=60, score=0.99)
        return [(0.0, face), (1.0, face), (2.0, face)]

    monkeypatch.setattr("snipzo.reframe.service.detect_clip_faces", fake_detect)
    updated, paths = reframe_project(
        project.id, settings, detector=FixedFaceDetector(), sample_fps=5.0
    )
    assert updated.status == ProjectStatus.REFRAMED
    assert len(paths) == 1
    assert paths[0].mode == "face"
    assert (updated.crops_dir / "clip-01.json").is_file()


def test_reframe_cli_center_fallback(sample_video: Path, tmp_path: Path) -> None:
    project, settings = _project_with_clip(tmp_path, sample_video)
    result = CliRunner().invoke(
        app, ["reframe", project.id, "--work-dir", str(settings.work_dir)]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Reframed 1 clips" in result.stdout
    # testsrc has no face; mode should be blur (if a detector loaded) or center.
    assert "clip-01" in result.stdout
