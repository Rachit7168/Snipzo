"""Shared fixtures for Snipzo tests."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def make_sample_video(
    dest: Path,
    *,
    duration: float = 2.0,
    width: int = 320,
    height: int = 180,
    fps: int = 30,
    audio: bool = True,
) -> Path:
    """Create a tiny test clip with ffmpeg (optional sine audio)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration}:size={width}x{height}:rate={fps}",
    ]
    if audio:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-c:a",
            "aac",
        ]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(dest)]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"failed to create sample video: {result.stderr}")
    return dest


@pytest.fixture
def sample_video_factory(tmp_path: Path) -> Callable[..., Path]:
    if not ffmpeg_available():
        pytest.skip("ffmpeg and ffprobe are required for this test")

    def _factory(**kwargs: object) -> Path:
        name = str(kwargs.pop("name", "sample.mp4"))
        # make_sample_video accepts concrete types; tests pass known keys.
        return make_sample_video(tmp_path / name, **kwargs)  # type: ignore[arg-type]

    return _factory


@pytest.fixture
def sample_video(sample_video_factory: Callable[..., Path]) -> Path:
    return sample_video_factory()
