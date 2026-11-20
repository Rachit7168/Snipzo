"""Face detectors used to drive a 9:16 crop. MediaPipe first, OpenCV fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class FaceBox:
    """Axis-aligned face rectangle in pixel coordinates."""

    x: float
    y: float
    w: float
    h: float
    score: float = 1.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0


@runtime_checkable
class FaceDetector(Protocol):
    """Detect faces in a BGR frame."""

    name: str

    def detect(self, frame: object) -> list[FaceBox]:
        """Return faces in pixel space, if any."""
        ...


def get_face_detector() -> FaceDetector | None:
    """Return the best available detector, or None if neither backend is installed."""
    mediapipe = _try_mediapipe()
    if mediapipe is not None:
        return mediapipe
    return _try_opencv()


class MediaPipeFaceDetector:
    """MediaPipe short-range face detection."""

    name = "mediapipe"

    def __init__(self, min_confidence: float = 0.5) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError("mediapipe is not installed") from exc
        self._mp = mp
        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=min_confidence,
        )

    def detect(self, frame: object) -> list[FaceBox]:
        import numpy as np

        if not isinstance(frame, np.ndarray) or frame.size == 0:
            return []
        height, width = frame.shape[:2]
        rgb = frame[:, :, ::-1]
        result = self._detector.process(rgb)
        if not result.detections:
            return []
        faces: list[FaceBox] = []
        for detection in result.detections:
            box = detection.location_data.relative_bounding_box
            score = 1.0
            if detection.score:
                score = float(detection.score[0])
            faces.append(
                FaceBox(
                    x=float(box.xmin) * width,
                    y=float(box.ymin) * height,
                    w=float(box.width) * width,
                    h=float(box.height) * height,
                    score=score,
                )
            )
        return faces


class OpenCVHaarFaceDetector:
    """Haar-cascade fallback when MediaPipe is unavailable."""

    name = "opencv-haar"

    def __init__(self) -> None:
        import cv2

        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(path)
        if cascade.empty():
            raise RuntimeError(f"Could not load Haar cascade from {path}")
        self._cv2 = cv2
        self._cascade = cascade

    def detect(self, frame: object) -> list[FaceBox]:
        import numpy as np

        if not isinstance(frame, np.ndarray) or frame.size == 0:
            return []
        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        raw = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        return [
            FaceBox(x=float(x), y=float(y), w=float(w), h=float(h))
            for x, y, w, h in raw
        ]


def _try_mediapipe() -> FaceDetector | None:
    try:
        return MediaPipeFaceDetector()
    except Exception:
        return None


def _try_opencv() -> FaceDetector | None:
    try:
        return OpenCVHaarFaceDetector()
    except Exception:
        return None
