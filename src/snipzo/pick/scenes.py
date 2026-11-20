"""Optional scene-cut detection via PySceneDetect."""

from __future__ import annotations

from pathlib import Path

from snipzo.errors import SnipzoError


def detect_scene_cuts(video_path: Path) -> list[float]:
    """Return scene-change timestamps in seconds, or [] if unavailable."""
    if not video_path.is_file():
        return []
    try:
        from scenedetect import ContentDetector, detect
    except ImportError:
        return []
    try:
        scenes = detect(str(video_path), ContentDetector(threshold=27.0))
    except Exception as exc:  # noqa: BLE001 - scene detection is best-effort
        raise SnipzoError(f"Scene detection failed: {exc}") from exc
    cuts: list[float] = []
    for pair in scenes:
        # scenedetect returns (start, end) Scene objects with get_seconds().
        start = pair[0]
        get_seconds = getattr(start, "get_seconds", None)
        seconds = float(get_seconds()) if callable(get_seconds) else 0.0
        if seconds > 0.05:
            cuts.append(seconds)
    return cuts
