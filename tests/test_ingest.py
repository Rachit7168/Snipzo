from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from snipzo.cli import app
from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.ingest import ingest_video
from snipzo.media import probe_video
from snipzo.projects import get_storage, resolve_project


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "data", _env_file=None)


def test_probe_video(sample_video: Path) -> None:
    info = probe_video(sample_video)
    assert info.width == 320
    assert info.height == 180
    assert info.has_audio is True
    assert info.fps == 30
    assert 1.5 <= info.duration <= 2.5


def test_ingest_creates_project_and_audio(sample_video: Path, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    project = ingest_video(sample_video, settings)

    assert project.root.is_dir()
    assert project.source_path.is_file()
    assert project.audio_path.is_file()
    assert project.project_json_path.is_file()
    assert project.audio_path.suffix == ".wav"
    # 2s of 16 kHz mono PCM is ~64 KiB plus a small WAV header.
    assert project.audio_path.stat().st_size >= 16_000 * 2

    loaded = resolve_project(project.id, get_storage(settings.work_dir))
    assert loaded.id == project.id
    assert loaded.source.width == 320
    assert loaded.source.has_audio is True


def test_resolve_project_by_path(sample_video: Path, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    project = ingest_video(sample_video, settings)
    storage = get_storage(tmp_path / "other")
    loaded = resolve_project(str(project.root), storage)
    assert loaded.id == project.id


def test_ingest_cli(sample_video: Path, tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    result = CliRunner().invoke(
        app, ["ingest", str(sample_video), "--work-dir", str(work_dir)]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Project " in result.stdout
    assert "created at" in result.stdout
    projects = [p for p in work_dir.iterdir() if p.is_dir()]
    assert len(projects) == 1
    assert (projects[0] / "project.json").is_file()
    assert (projects[0] / "audio.wav").is_file()


def test_ingest_rejects_missing_audio(
    sample_video_factory: Callable[..., Path], tmp_path: Path
) -> None:
    silent = sample_video_factory(name="silent.mp4", audio=False)
    with pytest.raises(SnipzoError, match="No audio stream"):
        ingest_video(silent, _settings(tmp_path))
