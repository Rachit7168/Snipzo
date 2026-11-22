"""Tests for friendly pipeline progress stage tracking."""

from __future__ import annotations

from pathlib import Path

from snipzo.api import jobs
from snipzo.api.db import session_scope
from snipzo.api.migrate import upgrade
from snipzo.api.tables import Job, ProjectRow, User
from snipzo.models import Project, ProjectStatus, VideoInfo
from tests.api_support import configure_env


def test_run_highlights_and_render_progress_messages_have_no_paths(
    monkeypatch, tmp_path: Path
) -> None:
    configure_env(tmp_path, monkeypatch)
    upgrade()

    with session_scope() as session:
        user = User(email="prog@example.com", password_hash="x")
        session.add(user)
        session.flush()
        proj = ProjectRow(
            id="proj-prog-1",
            user_id=user.id,
            title="Test",
            status="transcribing",
            source_kind="upload",
            source_filename="talk.mp4",
            rights_confirmed=True,
        )
        session.add(proj)
        job = Job(
            id="job-prog-1",
            project_id=proj.id,
            kind="pipeline",
            status="running",
            stage="transcribe",
            progress=0.167,
            message="Transcribing audio...",
        )
        session.add(job)

    recorded: list[tuple[str | None, str | None]] = []
    orig_update = jobs._update_job

    def spy_update(job_id: str, **kwargs):
        recorded.append((kwargs.get("stage"), kwargs.get("message")))
        return orig_update(job_id, **kwargs)

    def fake_run_pipeline(*_args, **kwargs):
        on_progress = kwargs["on_progress"]
        on_progress("ingest", "Project proj-prog-1 at /tmp/secret/work/proj-prog-1")
        on_progress("transcribe", "Skipping (transcript.json exists)")
        on_progress("pick", "Selecting highlight clips...")
        on_progress("metadata", "Generating titles and hashtags...")
        on_progress("reframe", "Computing 9:16 crop paths...")
        on_progress("render", "2 files in /tmp/secret/work/proj-prog-1/renders")
        return Project(
            id="proj-prog-1",
            work_dir=tmp_path / "work",
            source=VideoInfo(
                path=tmp_path / "talk.mp4",
                duration=30.0,
                width=1920,
                height=1080,
                fps=30.0,
                has_audio=True,
            ),
            status=ProjectStatus.COMPLETE,
        )

    monkeypatch.setattr(jobs, "_update_job", spy_update)
    monkeypatch.setattr(jobs, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(jobs, "sync_project_outputs", lambda *_a, **_kw: None)

    ok = jobs.run_highlights_and_render("job-prog-1")
    assert ok is True
    for _stage, msg in recorded:
        if msg:
            assert "/tmp/" not in msg
            assert "work/proj-prog-1" not in msg
    assert not any(stage in ("ingest", "transcribe") for stage, _ in recorded)
    assert any(stage == "pick" for stage, _ in recorded)
    assert any(stage == "metadata" for stage, _ in recorded)
    assert any(stage == "reframe" for stage, _ in recorded)
    assert any(stage == "render" for stage, _ in recorded)
