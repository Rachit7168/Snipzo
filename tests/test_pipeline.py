from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from snipzo.cli import app
from snipzo.config import Settings
from snipzo.models import ProjectStatus, Segment, Transcript, Word
from snipzo.pipeline import run_pipeline
from snipzo.transcribe.service import transcribe_project


class FakeTranscriber:
    def transcribe(self, audio_path: Path) -> Transcript:
        del audio_path
        words = [
            Word(text="What", start=0.0, end=0.3),
            Word(text="if", start=0.3, end=0.5),
            Word(text="you", start=0.5, end=0.7),
            Word(text="could", start=0.7, end=0.9),
            Word(text="finish", start=0.9, end=1.2),
            Word(text="this", start=1.2, end=1.4),
            Word(text="today?", start=1.4, end=1.8),
        ]
        return Transcript(
            language="en",
            duration=2.0,
            segments=[
                Segment(
                    start=0.0,
                    end=1.8,
                    text="What if you could finish this today?",
                    words=words,
                )
            ],
            words=words,
            backend="fake",
            model="test",
        )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        work_dir=tmp_path / "data",
        anthropic_api_key=None,
        caption_style="bold-yellow",
        clip_count=1,
        _env_file=None,
    )


def test_run_pipeline_end_to_end(
    sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        "snipzo.pipeline.transcribe_project",
        lambda ref, settings, storage=None, transcriber=None: transcribe_project(
            ref, settings, storage=storage, transcriber=FakeTranscriber()
        ),
    )
    project = run_pipeline(sample_video, settings, transcriber=FakeTranscriber())
    assert project.status == ProjectStatus.COMPLETE
    assert project.transcript_path.is_file()
    assert project.clips_path.is_file()
    assert (project.root / "metadata.json").is_file()
    renders = list(project.renders_dir.glob("*.mp4"))
    assert renders
    meta = list(project.renders_dir.glob("*.json"))
    assert meta
    from snipzo.media import probe_video

    info = probe_video(renders[0])
    assert info.width == 1080
    assert info.height == 1920
    assert info.codec == "h264"


def test_run_pipeline_is_resumable(
    sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    events: list[str] = []

    def on_progress(stage: str, message: str) -> None:
        events.append(f"{stage}:{message}")

    monkeypatch.setattr(
        "snipzo.pipeline.transcribe_project",
        lambda ref, settings, storage=None, transcriber=None: transcribe_project(
            ref, settings, storage=storage, transcriber=FakeTranscriber()
        ),
    )
    first = run_pipeline(sample_video, settings, transcriber=FakeTranscriber())
    events.clear()
    second = run_pipeline(
        None,
        settings,
        project_ref=first.id,
        transcriber=FakeTranscriber(),
        on_progress=on_progress,
    )
    assert second.id == first.id
    skips = [event for event in events if "Skipping" in event]
    assert len(skips) >= 4


def test_run_cli(
    sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work_dir = tmp_path / "work"
    monkeypatch.setattr(
        "snipzo.pipeline.transcribe_project",
        lambda ref, settings, storage=None, transcriber=None: transcribe_project(
            ref, settings, storage=storage, transcriber=FakeTranscriber()
        ),
    )
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(sample_video),
            "--work-dir",
            str(work_dir),
            "--top-n",
            "1",
            "--eval-csv",
            str(tmp_path / "ratings.csv"),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Done. Project" in result.stdout
    assert (tmp_path / "ratings.csv").is_file()
