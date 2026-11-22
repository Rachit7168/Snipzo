"""Error sanitization, request IDs, and 500 JSON responses."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from snipzo.api.app import create_app
from snipzo.api.errors import (
    GENERIC_JOB_ERROR,
    NO_AUDIO_ERROR,
    NO_SPEECH_ERROR,
    RENDER_ERROR,
    UNREADABLE_VIDEO_ERROR,
    sanitize_job_error,
    sanitize_publish_error,
)
from snipzo.api.youtube import YouTubeError
from snipzo.errors import SnipzoError
from tests.api_support import configure_env, make_client, register


def test_sanitize_job_error_hides_ffprobe_paths_and_ids() -> None:
    err = SnipzoError(
        "ffprobe could not read /tmp/snipzo-src-abc123/broken.mp4: "
        "[mov,mp4,m4a @ 0x55a] moov atom not found"
    )
    msg = sanitize_job_error(err)
    assert msg == UNREADABLE_VIDEO_ERROR
    assert "/tmp" not in msg
    assert "ffprobe" not in msg
    assert "moov atom" not in msg


def test_sanitize_job_error_hides_project_id_on_no_speech() -> None:
    err = SnipzoError("Transcription produced no text for project 2a3d490d75bd.")
    msg = sanitize_job_error(err)
    assert msg == NO_SPEECH_ERROR
    assert "2a3d490d75bd" not in msg


def test_sanitize_job_error_maps_no_audio_and_ffmpeg() -> None:
    assert (
        sanitize_job_error(SnipzoError("No audio stream found in /tmp/x.mp4."))
        == NO_AUDIO_ERROR
    )
    assert sanitize_job_error(SnipzoError("ffmpeg failed: exit code 1")) == RENDER_ERROR
    msg = sanitize_job_error(RuntimeError("boom at /home/app/secret"))
    assert msg == GENERIC_JOB_ERROR


def test_sanitize_job_error_preserves_billing_message() -> None:
    msg = (
        "This video is 2.0 min but your Free plan has 0.5 min left this month. "
        "Upgrade or use a shorter video."
    )
    assert sanitize_job_error(SnipzoError(msg)) == msg


def test_sanitize_publish_error_scrubs_raw_details() -> None:
    msg = sanitize_publish_error(
        YouTubeError("upload failed (500): /tmp/raw traceback")
    )
    assert "/tmp" not in msg
    assert "traceback" not in msg.lower()


def test_unhandled_500_returns_json_with_request_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_env(tmp_path, monkeypatch)
    app = create_app()

    @app.get("/_boom")
    def _boom() -> dict[str, str]:
        raise RuntimeError("secret internal failure /tmp/x")

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/_boom")
    assert res.status_code == 500
    body = res.json()
    assert body["detail"] == "Something went wrong on our side. Please try again."
    assert body["request_id"]
    assert res.headers.get("X-Request-Id") == body["request_id"]
    assert "secret internal" not in res.text
    assert "RuntimeError" not in res.text


def test_unconfigured_endpoints_never_leak_env_var_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SNIPZO_GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("SNIPZO_STRIPE_SECRET_KEY", raising=False)
    for client in make_client(tmp_path, monkeypatch):
        headers = register(client)

        yt = client.get("/youtube/connect", headers=headers)
        assert yt.status_code == 503
        assert "SNIPZO_" not in yt.text

        bill = client.post(
            "/billing/checkout", headers=headers, json={"plan": "creator"}
        )
        assert bill.status_code == 503
        assert "SNIPZO_" not in bill.text
