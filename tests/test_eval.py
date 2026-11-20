from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from snipzo.cli import app
from snipzo.eval.harness import (
    RATING_FIELDS,
    eval_summary,
    write_ratings_template,
)


def test_eval_summary_usable_percent(tmp_path: Path) -> None:
    rows = [
        {
            "video": "a.mp4",
            "project_id": "p1",
            "clip_id": "clip-01",
            "start": "0",
            "end": "20",
            "score": "0.9",
            "reason": "hook",
            "title": "A",
            "render_path": "a.mp4",
            "usable": "yes",
            "rating": "5",
            "notes": "",
        },
        {
            "video": "a.mp4",
            "project_id": "p1",
            "clip_id": "clip-02",
            "start": "30",
            "end": "55",
            "score": "0.7",
            "reason": "ok",
            "title": "B",
            "render_path": "b.mp4",
            "usable": "no",
            "rating": "2",
            "notes": "needed a trim",
        },
        {
            "video": "a.mp4",
            "project_id": "p1",
            "clip_id": "clip-03",
            "start": "60",
            "end": "90",
            "score": "0.8",
            "reason": "good",
            "title": "C",
            "render_path": "c.mp4",
            "usable": "",
            "rating": "",
            "notes": "",
        },
    ]
    path = write_ratings_template(tmp_path / "ratings.csv", rows)
    assert path.is_file()
    stats = eval_summary(path)
    assert stats["clips"] == 3
    assert stats["rated"] == 2
    assert stats["usable"] == 1
    assert stats["usable_percent"] == 50.0
    assert list(RATING_FIELDS)


def test_eval_summary_cli(tmp_path: Path) -> None:
    path = write_ratings_template(
        tmp_path / "ratings.csv",
        [
            {
                "video": "a.mp4",
                "project_id": "p1",
                "clip_id": "clip-01",
                "usable": "yes",
            }
        ],
    )
    result = CliRunner().invoke(app, ["eval", "summary", str(path)])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "1/1 rated clips usable without edits (100.0%)" in result.stdout
