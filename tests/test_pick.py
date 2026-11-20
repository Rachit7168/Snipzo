from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from snipzo.cli import app
from snipzo.config import Settings
from snipzo.models import (
    Project,
    ProjectStatus,
    Segment,
    Transcript,
    VideoInfo,
    Word,
)
from snipzo.pick.candidates import build_candidates
from snipzo.pick.scoring import (
    CandidateScore,
    HeuristicScorer,
    parse_claude_scores,
)
from snipzo.pick.sentences import sentences_from_transcript, snap_to_sentences
from snipzo.pick.service import pick_clips, select_top_clips
from snipzo.storage import LocalStorage


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        work_dir=tmp_path / "data",
        anthropic_api_key=None,
        clip_count=3,
        clip_min_seconds=20,
        clip_max_seconds=60,
        _env_file=None,
    )


def _words(start: float, end: float, text: str) -> list[Word]:
    tokens = text.split()
    step = (end - start) / max(len(tokens), 1)
    words: list[Word] = []
    for index, token in enumerate(tokens):
        words.append(
            Word(
                text=token,
                start=round(start + index * step, 3),
                end=round(start + (index + 1) * step, 3),
            )
        )
    return words


def fixture_transcript() -> Transcript:
    rows = [
        (0.0, 8.0, "And then we went to the office and sat down."),
        (8.2, 14.0, "It was a pretty ordinary morning overall."),
        (
            15.0,
            22.0,
            "What if you could cut your editing time in half?",
        ),
        (
            22.2,
            36.0,
            "Here's the secret I use every week when I turn talks into Shorts.",
        ),
        (
            36.2,
            50.0,
            "I never start in the middle of a sentence and I always lead with a hook.",
        ),
        (52.0, 60.0, "Most people never publish because they wait for perfect."),
        (
            60.2,
            74.0,
            "I realized the only way to grow is to ship something today.",
        ),
        (
            74.2,
            88.0,
            "You need to pick one idea, tell a complete story, and stop there.",
        ),
        (90.0, 98.0, "Anyway the recording setup is just a camera and a mic."),
        (
            98.2,
            110.0,
            "This is why a strong opening question changes everything.",
        ),
    ]
    segments: list[Segment] = []
    words: list[Word] = []
    for start, end, text in rows:
        segment_words = _words(start, end, text)
        segments.append(
            Segment(start=start, end=end, text=text, words=segment_words)
        )
        words.extend(segment_words)
    return Transcript(
        language="en",
        duration=110.0,
        segments=segments,
        words=words,
        backend="fixture",
        model="test",
    )


def _project_with_transcript(tmp_path: Path) -> Project:
    settings = _settings(tmp_path)
    storage = LocalStorage(settings.work_dir)
    project = Project(
        id="talk1",
        status=ProjectStatus.TRANSCRIBED,
        work_dir=settings.work_dir,
        language="en",
        source=VideoInfo(
            path=settings.work_dir / "talk1" / "source.mp4",
            duration=110.0,
            width=1280,
            height=720,
            fps=30,
            has_audio=True,
            codec="h264",
        ),
    )
    storage.save_project(project)
    storage.write_json(
        project.id, "transcript.json", fixture_transcript().model_dump(mode="json")
    )
    return project


def test_sentences_split_on_punctuation() -> None:
    sentences = sentences_from_transcript(fixture_transcript())
    assert len(sentences) >= 8
    assert sentences[2].text.startswith("What if")


def test_snap_never_starts_mid_word() -> None:
    sentences = sentences_from_transcript(fixture_transcript())
    # 16.3s is in the middle of "What if you could..." which starts at 15.0.
    start, end = snap_to_sentences(16.3, 48.5, sentences, duration=110.0, pad=0.2)
    assert start == pytest.approx(14.8)  # 15.0 - 0.2
    # End should land on a sentence end plus padding, not a mid-word time.
    ends = {round(sentence.end + 0.2, 3) for sentence in sentences}
    assert round(end, 3) in ends


def test_build_candidates_are_sentence_aligned() -> None:
    sentences = sentences_from_transcript(fixture_transcript())
    candidates = build_candidates(sentences, duration=110.0)
    assert candidates
    for candidate in candidates:
        assert 18.0 <= candidate.duration <= 61.0
        assert candidate.text[0].isupper() or candidate.text.startswith("And")


def test_heuristic_ranks_hooky_clips_higher() -> None:
    sentences = sentences_from_transcript(fixture_transcript())
    candidates = build_candidates(sentences, duration=110.0)
    scores = HeuristicScorer().score(candidates, fixture_transcript())
    by_id = {item.candidate_id: item for item in scores}
    hooky = max(scores, key=lambda item: item.score)
    # The weak office small-talk window should not be the top clip.
    top_text = next(c.text for c in candidates if c.id == hooky.candidate_id)
    assert (
        "What if" in top_text
        or "Most people" in top_text
        or "This is why" in top_text
    )
    assert by_id
    assert hooky.score > 0.4


def test_select_top_clips_deduplicates_overlaps() -> None:
    sentences = sentences_from_transcript(fixture_transcript())
    scores = [
        CandidateScore(
            candidate_id="a",
            start=15.0,
            end=50.0,
            score=0.9,
            reason="hook",
            hook_strength=0.9,
            standalone_clarity=0.8,
            emotion=0.7,
            length_score=0.8,
        ),
        CandidateScore(
            candidate_id="b",
            start=18.0,
            end=52.0,
            score=0.85,
            reason="overlap",
            hook_strength=0.8,
            standalone_clarity=0.8,
            emotion=0.7,
            length_score=0.8,
        ),
        CandidateScore(
            candidate_id="c",
            start=52.0,
            end=88.0,
            score=0.8,
            reason="second",
            hook_strength=0.8,
            standalone_clarity=0.8,
            emotion=0.6,
            length_score=0.8,
        ),
    ]
    clips = select_top_clips(scores, sentences, duration=110.0, top_n=5)
    assert len(clips) == 2
    assert clips[0].start == pytest.approx(14.8)
    assert clips[1].start >= 50.0


class FakeScorer:
    name = "fake"

    def score(self, candidates, transcript):  # type: ignore[no-untyped-def]
        del candidates, transcript
        # 16.3s sits mid-sentence in "What if you could..."; 48.5 is mid-window.
        return [
            CandidateScore(
                candidate_id="hook",
                start=16.3,
                end=48.5,
                score=0.95,
                reason="mocked hook",
                hook_strength=0.9,
                standalone_clarity=0.9,
                emotion=0.8,
                length_score=0.8,
            ),
            CandidateScore(
                candidate_id="second",
                start=52.0,
                end=88.0,
                score=0.7,
                reason="mocked second",
                hook_strength=0.6,
                standalone_clarity=0.7,
                emotion=0.5,
                length_score=0.8,
            ),
        ]


def test_pick_clips_writes_json_with_mocked_scorer(tmp_path: Path) -> None:
    project = _project_with_transcript(tmp_path)
    settings = _settings(tmp_path)
    updated, clipset = pick_clips(
        project.id, settings, scorer=FakeScorer(), use_scenes=False
    )
    assert updated.status == ProjectStatus.PICKED
    assert updated.clips_path.is_file()
    assert clipset.scorer == "fake"
    assert clipset.prompt_version == "v1"
    assert 1 <= len(clipset.clips) <= 3
    # Mid-word start from the mock must snap back to a sentence boundary.
    first = clipset.clips[0]
    sentences = sentences_from_transcript(fixture_transcript())
    starts = {round(sentence.start - 0.2, 3) for sentence in sentences}
    assert round(first.start, 3) in starts


def test_pick_cli_heuristic(tmp_path: Path) -> None:
    project = _project_with_transcript(tmp_path)
    settings = _settings(tmp_path)
    result = CliRunner().invoke(
        app, ["pick", project.id, "--work-dir", str(settings.work_dir), "--top-n", "2"]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Picked 2 clips" in result.stdout
    assert "heuristic" in result.stdout


def test_parse_claude_scores() -> None:
    sentences = sentences_from_transcript(fixture_transcript())
    candidates = build_candidates(sentences, duration=110.0)
    payload = {
        "content": [
            {
                "type": "text",
                "text": (
                    '{"clips":[{"id":"'
                    + candidates[0].id
                    + '","start":15.0,"end":50.0,'
                    '"hook_strength":0.9,"standalone_clarity":0.8,'
                    '"emotion":0.7,"length_score":0.8,"score":0.84,'
                    '"reason":"Opens with a question."}]}'
                ),
            }
        ]
    }
    scores = parse_claude_scores(payload, candidates)
    assert len(scores) == 1
    assert scores[0].reason == "Opens with a question."
    assert scores[0].score == 0.84
