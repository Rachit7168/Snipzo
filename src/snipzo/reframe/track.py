"""Build a smoothed 9:16 crop path from optional face detections."""

from __future__ import annotations

from collections.abc import Sequence

from snipzo.models import Clip, CropKeyframe, CropPath
from snipzo.reframe.detect import FaceBox, FaceDetector
from snipzo.reframe.geometry import (
    center_origin,
    crop_size,
    origin_from_point,
    smooth_series,
)


def sample_times(start: float, end: float, fps: float = 5.0) -> list[float]:
    """Timestamps at which to sample faces for a clip."""
    if end <= start:
        return [start]
    step = 1.0 / fps if fps > 0 else 0.2
    times: list[float] = []
    t = start
    while t < end:
        times.append(round(t, 3))
        t += step
    if not times or times[-1] < end - 0.01:
        times.append(round(end, 3))
    return times


def pick_primary_face(faces: Sequence[FaceBox]) -> FaceBox | None:
    """Prefer the largest, highest-scoring face."""
    if not faces:
        return None
    return max(faces, key=lambda face: (face.w * face.h, face.score))


def build_crop_path(
    clip: Clip,
    *,
    width: int,
    height: int,
    detections: Sequence[tuple[float, FaceBox | None]],
    smooth_alpha: float = 0.3,
) -> CropPath:
    """Turn per-timestamp face detections into a clamped, smoothed crop path."""
    crop_w, crop_h = crop_size(width, height)
    cx0, cy0 = center_origin(width, height, crop_w, crop_h)
    if not detections:
        return CropPath(
            clip_id=clip.id,
            mode="center",
            source_width=width,
            source_height=height,
            keyframes=[
                CropKeyframe(t=clip.start, x=cx0, y=cy0, w=crop_w, h=crop_h),
                CropKeyframe(t=clip.end, x=cx0, y=cy0, w=crop_w, h=crop_h),
            ],
        )

    times = [t for t, _ in detections]
    raw_x: list[float] = []
    raw_y: list[float] = []
    seen_face = False
    last_origin: tuple[float, float] = (cx0, cy0)
    for _t, face in detections:
        if face is not None:
            last_origin = origin_from_point(
                face.cx, face.cy, width, height, crop_w, crop_h
            )
            seen_face = True
        raw_x.append(last_origin[0])
        raw_y.append(last_origin[1])

    if not seen_face:
        return CropPath(
            clip_id=clip.id,
            mode="blur",
            source_width=width,
            source_height=height,
            keyframes=[
                CropKeyframe(t=t, x=cx0, y=cy0, w=crop_w, h=crop_h) for t in times
            ],
        )

    xs = smooth_series(raw_x, alpha=smooth_alpha)
    ys = smooth_series(raw_y, alpha=smooth_alpha)
    keyframes = [
        CropKeyframe(t=t, x=round(x, 2), y=round(y, 2), w=crop_w, h=crop_h)
        for t, x, y in zip(times, xs, ys, strict=True)
    ]
    return CropPath(
        clip_id=clip.id,
        mode="face",
        source_width=width,
        source_height=height,
        keyframes=keyframes,
    )


def detect_clip_faces(
    video_path: str,
    clip: Clip,
    detector: FaceDetector,
    *,
    fps: float = 5.0,
) -> list[tuple[float, FaceBox | None]]:
    """Sample frames from `video_path` and run `detector` on each."""
    try:
        import cv2
    except ImportError:
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return []
    samples: list[tuple[float, FaceBox | None]] = []
    try:
        for timestamp in sample_times(clip.start, clip.end, fps=fps):
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000.0)
            ok, frame = cap.read()
            if not ok:
                samples.append((timestamp, None))
                continue
            face = pick_primary_face(detector.detect(frame))
            samples.append((timestamp, face))
    finally:
        cap.release()
    return samples
