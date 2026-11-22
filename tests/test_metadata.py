from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from snipzo.cli import app
from snipzo.config import Settings
from snipzo.metadata.generate import (
    HeuristicMetadataGenerator,
    parse_claude_metadata,
    validate_metadata,
)
from snipzo.metadata.service import generate_metadata
from snipzo.models import (
    Clip,
    ClipMetadata,
    ClipSet,
    Project,
    ProjectStatus,
    Transcript,
    VideoInfo,
    Word,
)
from snipzo.storage import LocalStorage


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "data", anthropic_api_key=None, _env_file=None)


def _project(tmp_path: Path) -> tuple[Project, Settings]:
    settings = _settings(tmp_path)
    storage = LocalStorage(settings.work_dir)
    project = Project(
        id="meta1",
        status=ProjectStatus.RENDERED,
        work_dir=settings.work_dir,
        language="en",
        source=VideoInfo(
            path=settings.work_dir / "meta1" / "source.mp4",
            duration=40.0,
            width=1280,
            height=720,
            fps=30,
            has_audio=True,
        ),
    )
    storage.save_project(project)
    clip = Clip(
        id="clip-01",
        start=0.0,
        end=30.0,
        score=0.9,
        reason="hook",
    )
    storage.write_json(
        project.id,
        "clips.json",
        ClipSet(clips=[clip], scorer="test").model_dump(mode="json"),
    )
    words = [
        Word(text="What", start=0.0, end=0.3),
        Word(text="if", start=0.3, end=0.5),
        Word(text="you", start=0.5, end=0.7),
        Word(text="could", start=0.7, end=0.9),
        Word(text="cut", start=0.9, end=1.1),
        Word(text="your", start=1.1, end=1.3),
        Word(text="editing", start=1.3, end=1.7),
        Word(text="time", start=1.7, end=1.9),
        Word(text="in", start=1.9, end=2.1),
        Word(text="half?", start=2.1, end=2.5),
        Word(text="Here's", start=2.6, end=2.9),
        Word(text="the", start=2.9, end=3.0),
        Word(text="secret", start=3.0, end=3.4),
        Word(text="I", start=3.4, end=3.5),
        Word(text="use", start=3.5, end=3.7),
        Word(text="every", start=3.7, end=3.9),
        Word(text="week.", start=3.9, end=4.2),
    ]
    storage.write_json(
        project.id,
        "transcript.json",
        Transcript(language="en", duration=40.0, words=words).model_dump(mode="json"),
    )
    return project, settings


def test_heuristic_title_and_shorts_hashtag() -> None:
    project, settings = _project(Path("/tmp"))  # unused path overwritten below
    # Build isolated objects instead.
    clip = Clip(id="clip-01", start=0, end=30, score=0.9, reason="hook")
    words = [
        Word(text="What", start=0.0, end=0.3),
        Word(text="if", start=0.3, end=0.5),
        Word(text="you", start=0.5, end=0.7),
        Word(text="could", start=0.7, end=0.9),
        Word(text="cut", start=0.9, end=1.2),
        Word(text="editing", start=1.2, end=1.6),
        Word(text="time", start=1.6, end=1.9),
        Word(text="in", start=1.9, end=2.1),
        Word(text="half?", start=2.1, end=2.5),
    ]
    transcript = Transcript(language="en", duration=30, words=words)
    meta = HeuristicMetadataGenerator().generate(clip, transcript, "en")
    assert len(meta.title) <= 100
    assert meta.title.lower().startswith("what if")
    assert "#Shorts" in meta.hashtags
    assert "shorts" in meta.tags
    assert meta.hook_title
    assert len(meta.hook_title) <= 80


def test_validate_metadata_enforces_limits() -> None:
    meta = validate_metadata(
        ClipMetadata(
            clip_id="clip-01",
            title="T" * 140,
            description="A useful tip.",
            hashtags=["editing"],
            tags=["Editing"],
        )
    )
    assert len(meta.title) <= 100
    assert meta.title.endswith("...")
    assert "#Shorts" in meta.hashtags
    assert "shorts" in meta.tags
    assert "#Shorts" in meta.description or "shorts" in meta.description.lower()


def test_parse_claude_metadata() -> None:
    payload = {
        "content": [
            {
                "type": "text",
                "text": (
                    '{"title":"Cut your editing time in half",'
                    '"hook_title":"Cut editing time in half",'
                    '"description":"A fast way to edit talks.",'
                    '"hashtags":["#Shorts","#editing"],'
                    '"tags":["shorts","editing"]}'
                ),
            }
        ]
    }
    meta = parse_claude_metadata(payload, "clip-01")
    assert meta.clip_id == "clip-01"
    assert meta.title == "Cut your editing time in half"
    assert "#Shorts" in validate_metadata(meta).hashtags


class FakeGenerator:
    name = "fake"

    def generate(self, clip, transcript, language):  # type: ignore[no-untyped-def]
        del transcript, language
        return ClipMetadata(
            clip_id=clip.id,
            title="A mocked hook title for the clip",
            hook_title="A mocked hook title",
            description="Mock description",
            hashtags=["#Shorts", "#mock"],
            tags=["shorts", "mock"],
            generator=self.name,
        )


def test_generate_metadata_writes_json(tmp_path: Path) -> None:
    project, settings = _project(tmp_path)
    updated, items = generate_metadata(
        project.id, settings, generator=FakeGenerator()
    )
    path = updated.renders_dir / "clip-01.json"
    assert path.is_file()
    saved = ClipMetadata.model_validate_json(path.read_text(encoding="utf-8"))
    assert saved.title == "A mocked hook title for the clip"
    assert saved.generator == "fake"
    # Hook title is copied onto the clip for later renders.
    from snipzo.pick.service import load_clips

    clips = load_clips(updated)
    assert clips.clips[0].hook_title == "A mocked hook title"
    assert len(items) == 1


def test_metadata_cli(tmp_path: Path) -> None:
    project, settings = _project(tmp_path)
    result = CliRunner().invoke(
        app, ["metadata", project.id, "--work-dir", str(settings.work_dir)]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Wrote metadata for 1 clips" in result.stdout
    assert (settings.work_dir / project.id / "renders" / "clip-01.json").is_file()


def test_voa_filler_transcript_produces_clean_title_and_hashtags() -> None:
    clip = Clip(id="clip-01", start=0.0, end=45.0, score=0.7, reason="hook")
    spoken = (
        "you know, like coming again and stuff like this. And so I said, like, "
        "if there's any chance, I can help him. Yeah, that was my motivation. "
        "So what do you see your foundation in Sierra Leone in five years? "
        "At the end of the day, like, you never know what happens. "
        "Because my personal goal is definitely education and infrastructure."
    )
    words = [
        Word(text=tok, start=idx * 0.4, end=idx * 0.4 + 0.35)
        for idx, tok in enumerate(spoken.split())
    ]
    transcript = Transcript(language="en", duration=45.0, words=words)
    meta = HeuristicMetadataGenerator().generate(clip, transcript, "en")

    lower_title = meta.title.lower()
    assert not lower_title.startswith("you know")
    assert "stuff like" not in lower_title
    assert meta.hook_title is not None
    assert not meta.hook_title.lower().startswith("you know")
    assert meta.hashtags[0] == "#Shorts"

    forbidden = {
        "#like",
        "#know",
        "#what",
        "#day",
        "#end",
        "#never",
        "#that's",
        "#thats",
        "#i'm",
        "#im",
        "#want",
        "#because",
        "#stuff",
    }
    assert not (forbidden & {tag.lower() for tag in meta.hashtags}), meta.hashtags


def test_ramble_without_clean_sentence_uses_keyphrase_headline() -> None:
    clip = Clip(id="clip-02", start=0.0, end=25.0, score=0.5, reason="topic")
    spoken = (
        "Education is more like it takes a long time to be honest. "
        "That's, that's not from today to tomorrow. "
        "But what I want to really achieve very early is the infrastructure. "
        "Because we all know you're African too. So"
    )
    words = [
        Word(text=tok, start=idx * 0.4, end=idx * 0.4 + 0.35)
        for idx, tok in enumerate(spoken.split())
    ]
    transcript = Transcript(language="en", duration=25.0, words=words)
    meta = HeuristicMetadataGenerator().generate(clip, transcript, "en")

    assert "more like" not in meta.title.lower()
    assert "takes a long" not in meta.title.lower()
    assert any(
        term in meta.title.lower()
        for term in ("infrastructure", "education", "african")
    )
    tags_lower = {tag.lower() for tag in meta.hashtags}
    assert "#like" not in tags_lower
    assert "#because" not in tags_lower
    assert "#want" not in tags_lower
    assert "#that's" not in tags_lower


def test_require_llm_metadata_fails_loudly_without_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from snipzo.errors import SnipzoError
    from snipzo.metadata.service import get_generator
    from snipzo.pick.service import get_scorer

    strict = Settings(
        work_dir=tmp_path / "data",
        anthropic_api_key=None,
        require_llm_metadata=True,
        _env_file=None,
    )
    with pytest.raises(SnipzoError, match="SNIPZO_ANTHROPIC_API_KEY"):
        get_generator(strict)
    with pytest.raises(SnipzoError, match="SNIPZO_ANTHROPIC_API_KEY"):
        get_scorer(strict)

    project, _ = _project(tmp_path)
    with pytest.raises(SnipzoError, match="SNIPZO_ANTHROPIC_API_KEY"):
        generate_metadata(project.id, strict)

    # When API key is set, Claude generator is selected cleanly.
    with_key = Settings(
        work_dir=tmp_path / "data",
        anthropic_api_key="sk-ant-test-key",
        require_llm_metadata=True,
        _env_file=None,
    )
    gen = get_generator(with_key)
    assert gen.name == "claude"
    scorer = get_scorer(with_key)
    assert scorer.name == "claude"
    monkeypatch.undo()
