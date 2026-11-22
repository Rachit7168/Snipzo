"""Helpers for API tests: an isolated SQLite DB, local blobs, and eager Celery."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from snipzo.models import Segment, Transcript, Word

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("celery")

from fastapi.testclient import TestClient  # noqa: E402


class FakeTranscriber:
    def transcribe(self, audio_path: Path) -> Transcript:
        del audio_path
        texts = "What if you could finish this today? Nobody tells you this.".split()
        words = [
            Word(text=text, start=index * 0.3, end=index * 0.3 + 0.28)
            for index, text in enumerate(texts)
        ]
        return Transcript(
            language="en",
            duration=words[-1].end,
            segments=[
                Segment(start=0.0, end=words[-1].end, text=" ".join(texts), words=words)
            ],
            words=words,
            backend="fake",
            model="test",
        )


def configure_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from snipzo.api.db import reset_engine_cache
    from snipzo.api.settings import get_api_settings
    from snipzo.config import get_settings

    env = {
        "SNIPZO_DATABASE_URL": f"sqlite:///{tmp_path / 'api.db'}",
        "SNIPZO_CELERY_EAGER": "true",
        "SNIPZO_STORAGE_BACKEND": "local",
        "SNIPZO_STORAGE_DIR": str(tmp_path / "blobs"),
        "SNIPZO_WORK_DIR": str(tmp_path / "work"),
        "SNIPZO_SECRET_KEY": "test-secret",
        "SNIPZO_PUBLIC_API_URL": "http://testserver",
        "SNIPZO_CLIP_COUNT": "1",
        "SNIPZO_ANTHROPIC_API_KEY": "",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    get_api_settings.cache_clear()
    get_settings.cache_clear()
    reset_engine_cache()

    from snipzo.api import jobs

    monkeypatch.setattr(jobs, "transcriber_factory", lambda settings: FakeTranscriber())


def make_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    configure_env(tmp_path, monkeypatch)
    from snipzo.api.app import create_app
    from snipzo.api.migrate import upgrade

    upgrade()
    with TestClient(create_app()) as client:
        yield client

    from snipzo.api.db import reset_engine_cache
    from snipzo.api.settings import get_api_settings
    from snipzo.config import get_settings

    get_api_settings.cache_clear()
    get_settings.cache_clear()
    reset_engine_cache()


def register(client: TestClient, email: str = "a@example.com") -> dict[str, str]:
    response = client.post(
        "/auth/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def upload(
    client: TestClient, headers: dict[str, str], video: Path, **form: str
) -> dict[str, object]:
    data = {"rights_confirmed": "true", **form}
    with video.open("rb") as handle:
        response = client.post(
            "/projects",
            headers=headers,
            data=data,
            files={"file": (video.name, handle, "video/mp4")},
        )
    assert response.status_code == 201, response.text
    payload: dict[str, object] = response.json()
    return payload
