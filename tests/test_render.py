from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from snipzo.cli import app
from snipzo.config import Settings
from snipzo.media import probe_video
from snipzo.models import (
    Clip,
    ClipSet,
    Project,
    ProjectStatus,
    Transcript,
    VideoInfo,
    Word,
)
from snipzo.render.ass import (
    ass_time,
    build_ass,
    group_words,
    hook_title_from_words,
    words_for_clip,
)
from snipzo.render.filters import build_filter_complex, is_static_crop
from snipzo.render.service import render_project
from snipzo.render.styles import get_style
from snipzo.storage import LocalStorage


def test_ass_time_format() -> None:
    assert ass_time(0) == "0:00:00.00"
    assert ass_time(1.5) == "0:00:01.50"
    assert ass_time(61.259) == "0:01:01.26"


def test_group_words_keeps_two_to_four() -> None:
    words = [
        Word(text=f"w{i}", start=i * 0.2, end=i * 0.2 + 0.2) for i in range(8)
    ]
    groups = group_words(words)
    assert groups
    assert all(2 <= len(group) <= 4 for group in groups[:-1])
    assert all(1 <= len(group) <= 4 for group in groups)
    # 8 words should not leave a stray single-word group.
    assert len(groups[-1]) >= 2


def test_build_ass_has_hook_and_highlighted_words() -> None:
    clip = Clip(id="clip-01", start=5.0, end=10.0, score=0.8, reason="test")
    words = [
        Word(text="What", start=0.0, end=0.3),
        Word(text="if", start=0.3, end=0.5),
        Word(text="you", start=0.5, end=0.8),
        Word(text="never", start=0.8, end=1.1),
        Word(text="stop?", start=1.1, end=1.5),
    ]
    style = get_style("bold-yellow")
    document = build_ass(
        words=words, clip=clip, style=style, hook_title="What if you never stop?"
    )
    assert "PlayResX: 1080" in document
    assert "PlayResY: 1920" in document
    assert "WHAT IF YOU NEVER STOP?" in document
    assert "{\\c&H0000F5FF&}" in document
    assert "Style: Hook" in document
    assert "0:00:00.00" in document


def test_hook_title_falls_back_to_first_words() -> None:
    clip = Clip(id="clip-01", start=0, end=5, score=0.5, reason="t")
    words = [
        Word(text="Here", start=0, end=0.2),
        Word(text="is", start=0.2, end=0.3),
        Word(text="the", start=0.3, end=0.4),
        Word(text="secret.", start=0.4, end=0.7),
        Word(text="Later", start=0.8, end=1.0),
    ]
    assert hook_title_from_words(clip, words) == "Here is the secret."


def test_words_for_clip_are_relative() -> None:
    clip = Clip(id="clip-01", start=10.0, end=12.0, score=0.5, reason="t")
    transcript = Transcript(
        language="en",
        duration=20,
        words=[
            Word(text="Hello", start=10.0, end=10.4),
            Word(text="world", start=10.4, end=11.0),
            Word(text="later", start=15.0, end=15.4),
        ],
    )
    words = words_for_clip(transcript, clip)
    assert [word.text for word in words] == ["Hello", "world"]
    assert words[0].start == 0.0
    assert words[1].end == 1.0


def test_filter_complex_includes_loudnorm_and_progress() -> None:
    clip = Clip(id="clip-01", start=0, end=2, score=0.5, reason="t")
    from snipzo.models import CropKeyframe, CropPath

    crop = CropPath(
        clip_id="clip-01",
        mode="center",
        source_width=320,
        source_height=180,
        keyframes=[
            CropKeyframe(t=0, x=10, y=0, w=100, h=180),
            CropKeyframe(t=2, x=10, y=0, w=100, h=180),
        ],
    )
    assert is_static_crop(crop)
    graph = build_filter_complex(
        clip=clip,
        crop=crop,
        style=get_style("bold-yellow"),
        ass_path=Path("/tmp/captions.ass"),
        sendcmd_path=None,
    )
    assert "loudnorm" in graph
    assert "1080" in graph and "1920" in graph
    assert "drawbox" in graph
    assert "subtitles=" in graph


def _render_project(tmp_path: Path, video: Path) -> tuple[Project, Settings]:
    settings = Settings(
        work_dir=tmp_path / "data", caption_style="bold-yellow", _env_file=None
    )
    storage = LocalStorage(settings.work_dir)
    project = Project(
        id="short1",
        status=ProjectStatus.REFRAMED,
        work_dir=settings.work_dir,
        language="en",
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
    stored = storage.copy_into(project.id, video, video.name)
    project = project.model_copy(
        update={"source": project.source.model_copy(update={"path": stored})}
    )
    storage.save_project(project)
    clip = Clip(id="clip-01", start=0.0, end=2.0, score=0.9, reason="demo")
    storage.write_json(
        project.id,
        "clips.json",
        ClipSet(clips=[clip], scorer="test").model_dump(mode="json"),
    )
    words = [
        Word(text="Hello", start=0.0, end=0.5),
        Word(text="there", start=0.5, end=1.0),
        Word(text="friends", start=1.0, end=1.6),
        Word(text="today.", start=1.6, end=2.0),
    ]
    storage.write_json(
        project.id,
        "transcript.json",
        Transcript(
            language="en", duration=2.0, words=words, segments=[]
        ).model_dump(mode="json"),
    )
    return project, settings


def test_render_writes_1080x1920_h264(sample_video: Path, tmp_path: Path) -> None:
    project, settings = _render_project(tmp_path, sample_video)
    updated, renders = render_project(project.id, settings)
    assert updated.status == ProjectStatus.RENDERED
    assert len(renders) == 1
    rendered = renders[0].path
    assert rendered.is_file()
    info = probe_video(rendered)
    assert info.width == 1080
    assert info.height == 1920
    assert abs(info.fps - 30) < 0.1
    assert 1.5 <= info.duration <= 2.5
    assert info.codec == "h264"
    assert info.has_audio is True


def test_render_cli(sample_video: Path, tmp_path: Path) -> None:
    project, settings = _render_project(tmp_path, sample_video)
    result = CliRunner().invoke(
        app, ["render", project.id, "--work-dir", str(settings.work_dir)]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Rendered 1 Shorts" in result.stdout
    assert (settings.work_dir / project.id / "renders" / "clip-01.mp4").is_file()
