from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from snipzo.cli import app
from snipzo.config import Settings
from snipzo.errors import SnipzoError
from snipzo.ingest import ingest_video
from snipzo.models import Project, Segment, Transcript, Word
from snipzo.transcribe.deepgram import parse_deepgram_response
from snipzo.transcribe.service import get_transcriber, transcribe_project


class FakeTranscriber:
    def __init__(self, transcript: Transcript) -> None:
        self.transcript = transcript
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path) -> Transcript:
        self.calls.append(audio_path)
        return self.transcript


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "data", _env_file=None)


def _transcript() -> Transcript:
    words = [
        Word(text="Hello", start=0.0, end=0.4, confidence=0.99),
        Word(text="world", start=0.4, end=0.8, confidence=0.98),
    ]
    return Transcript(
        language="en",
        duration=2.0,
        segments=[
            Segment(
                start=0.0, end=0.8, text="Hello world", words=words, confidence=0.99
            )
        ],
        words=words,
        backend="fake",
        model="test",
    )


def test_transcribe_project_writes_json(
    sample_video: Path, tmp_path: Path
) -> None:
    settings = _settings(tmp_path)
    project = ingest_video(sample_video, settings)
    fake = FakeTranscriber(_transcript())

    updated, transcript = transcribe_project(
        project.id, settings, transcriber=fake
    )

    assert updated.status == "transcribed"
    assert updated.language == "en"
    assert updated.transcript_path.is_file()
    saved = Transcript.model_validate_json(
        updated.transcript_path.read_text(encoding="utf-8")
    )
    assert saved.words[0].text == "Hello"
    assert saved.words[1].end == 0.8
    assert len(fake.calls) == 1
    assert fake.calls[0] == project.audio_path
    assert transcript.backend == "fake"


def test_transcribe_cli(
    sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    project = ingest_video(sample_video, settings)
    fake = FakeTranscriber(_transcript())
    monkeypatch.setattr(
        "snipzo.transcribe.service.get_transcriber",
        lambda _settings: fake,
    )

    result = CliRunner().invoke(
        app,
        ["transcribe", project.id, "--work-dir", str(settings.work_dir)],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "2 words" in result.stdout
    assert (settings.work_dir / project.id / "transcript.json").is_file()


def test_transcribe_requires_audio(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    project_dir = settings.work_dir / "missing"
    project_dir.mkdir(parents=True)
    project = Project.model_validate(
        {
            "id": "missing",
            "status": "ingested",
            "work_dir": str(settings.work_dir),
            "source": {
                "path": str(project_dir / "source.mp4"),
                "duration": 1.0,
                "width": 320,
                "height": 180,
                "fps": 30,
                "has_audio": True,
            },
        }
    )
    (project_dir / "project.json").write_text(
        project.model_dump_json(), encoding="utf-8"
    )
    with pytest.raises(SnipzoError, match="No extracted audio"):
        transcribe_project(
            "missing", settings, transcriber=FakeTranscriber(_transcript())
        )


def test_get_transcriber_deepgram_requires_key(tmp_path: Path) -> None:
    settings = Settings(
        work_dir=tmp_path,
        transcriber="deepgram",
        deepgram_api_key=None,
        _env_file=None,
    )
    with pytest.raises(SnipzoError, match="DEEPGRAM_API_KEY"):
        get_transcriber(settings)


def test_parse_deepgram_response() -> None:
    payload = {
        "metadata": {"duration": 1.2, "model_info": {"name": "nova-2"}},
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": "Hello world",
                            "languages": ["en"],
                            "words": [
                                {
                                    "word": "hello",
                                    "punctuated_word": "Hello",
                                    "start": 0.0,
                                    "end": 0.4,
                                    "confidence": 0.99,
                                },
                                {
                                    "word": "world",
                                    "punctuated_word": "world",
                                    "start": 0.4,
                                    "end": 0.9,
                                    "confidence": 0.95,
                                },
                            ],
                        }
                    ]
                }
            ],
            "utterances": [
                {
                    "transcript": "Hello world",
                    "start": 0.0,
                    "end": 0.9,
                    "confidence": 0.97,
                    "words": [
                        {
                            "word": "hello",
                            "punctuated_word": "Hello",
                            "start": 0.0,
                            "end": 0.4,
                            "confidence": 0.99,
                        },
                        {
                            "word": "world",
                            "punctuated_word": "world",
                            "start": 0.4,
                            "end": 0.9,
                            "confidence": 0.95,
                        },
                    ],
                }
            ],
        },
    }
    transcript = parse_deepgram_response(payload)
    assert transcript.backend == "deepgram"
    assert transcript.language == "en"
    assert [word.text for word in transcript.words] == ["Hello", "world"]
    assert transcript.segments[0].text == "Hello world"
    assert transcript.duration == 1.2
