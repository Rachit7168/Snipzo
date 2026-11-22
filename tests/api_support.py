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



class FakeYoutubeDownloader:
    """In-memory yt-dlp stand-in. Tests set ``media_path`` for a successful download."""

    def __init__(self) -> None:
        self.probes: list[str] = []
        self.downloads: list[str] = []
        self.media_path: Path | None = None
        self.by_id: dict[str, object] = {}
        self.errors: dict[str, str] = {}
        self.default_duration = 60.0
        self.default_title = "Test YouTube video"

    def _video_id(self, url: str) -> str:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        if "youtu.be" in (parsed.netloc or ""):
            return parsed.path.strip("/").split("/", 1)[0]
        query = parse_qs(parsed.query)
        if query.get("v"):
            return query["v"][0]
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed", "v", "e"}:
            return parts[1]
        return url

    def probe(self, url: str) -> object:
        from snipzo.api.ytdlp import YoutubeUnavailable, YoutubeVideoInfo
        from snipzo.youtube_url import canonical_watch_url, default_thumbnail_url

        self.probes.append(url)
        video_id = self._video_id(url)
        if video_id in self.errors:
            raise YoutubeUnavailable(self.errors[video_id])
        existing = self.by_id.get(video_id)
        if isinstance(existing, YoutubeVideoInfo):
            return existing
        return YoutubeVideoInfo(
            video_id=video_id,
            title=self.default_title,
            duration=self.default_duration,
            thumbnail_url=default_thumbnail_url(video_id)
            if len(video_id) == 11
            else "https://i.ytimg.com/vi/dQw4w9wg9cQ/hqdefault.jpg",
            url=canonical_watch_url(video_id) if len(video_id) == 11 else url,
        )

    def download(self, url: str, dest: Path, *, max_bytes: int, timeout: int) -> Path:
        del max_bytes, timeout
        self.downloads.append(url)
        if self.media_path is None or not self.media_path.is_file():
            raise AssertionError(
                "FakeYoutubeDownloader.download needs media_path; "
                "tests must not hit the network."
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.media_path.read_bytes())
        return dest


def configure_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> FakeYoutubeDownloader:
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
        "SNIPZO_FREE_VIDEOS_PER_MONTH": "3",
        "SNIPZO_YOUTUBE_IMPORT_DOWNLOADER": "yt-dlp",
        "SNIPZO_MAX_UPLOAD_MB": "2048",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    get_api_settings.cache_clear()
    get_settings.cache_clear()
    reset_engine_cache()

    from snipzo.api import jobs, ytdlp

    monkeypatch.setattr(jobs, "transcriber_factory", lambda settings: FakeTranscriber())
    # Never let tests hit the real YouTube network.
    fake = FakeYoutubeDownloader()
    monkeypatch.setattr(ytdlp, "downloader_factory", lambda: fake)
    return fake


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
