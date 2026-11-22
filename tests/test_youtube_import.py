from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from snipzo.api.ytdlp import YoutubeVideoInfo  # noqa: E402
from tests.api_support import FakeYoutubeDownloader, make_client, register  # noqa: E402

VIDEO = "dQw4w9wg9cQ"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from make_client(tmp_path, monkeypatch)


def _downloader() -> FakeYoutubeDownloader:
    from snipzo.api import ytdlp

    fake = ytdlp.get_downloader()
    assert isinstance(fake, FakeYoutubeDownloader)
    return fake


def test_youtube_url_creates_project_with_preview(
    client: TestClient, sample_video: Path
) -> None:
    fake = _downloader()
    fake.media_path = sample_video
    fake.by_id[VIDEO] = YoutubeVideoInfo(
        video_id=VIDEO,
        title="Public domain interview",
        duration=45.0,
        thumbnail_url="https://i.ytimg.com/vi/dQw4w9wg9cQ/hqdefault.jpg",
        url=f"https://www.youtube.com/watch?v={VIDEO}",
    )
    headers = register(client)
    response = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "true",
            "source_url": f"https://youtu.be/{VIDEO}?t=12&list=PLxxxx",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_kind"] == "youtube"
    assert body["source_page_url"] == f"https://www.youtube.com/watch?v={VIDEO}"
    assert body["source_title"] == "Public domain interview"
    assert body["source_thumbnail_url"].endswith("hqdefault.jpg")
    assert body["title"] == "Public domain interview"
    assert fake.probes
    assert fake.downloads == [f"https://www.youtube.com/watch?v={VIDEO}"]
    # Eager workers run the pipeline on the mocked file.
    detail = client.get(f"/projects/{body['id']}", headers=headers).json()
    assert detail["status"] == "complete", detail
    assert detail["job"]["status"] == "succeeded"


def test_youtube_url_requires_rights(client: TestClient) -> None:
    headers = register(client)
    response = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "false",
            "source_url": f"https://www.youtube.com/watch?v={VIDEO}",
        },
    )
    assert response.status_code == 400
    assert "rights" in response.json()["detail"]
    assert _downloader().probes == []


def test_playlist_tiktok_and_restrictions_are_friendly(client: TestClient) -> None:
    fake = _downloader()
    headers = register(client)

    playlist = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "true",
            "source_url": "https://www.youtube.com/playlist?list=PLxxxx",
        },
    )
    assert playlist.status_code == 400
    assert "playlist" in playlist.json()["detail"].lower()
    assert "yt-dlp" not in playlist.json()["detail"].lower()

    tiktok = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "true",
            "source_url": "https://www.tiktok.com/@user/video/123",
        },
    )
    assert tiktok.status_code == 400
    assert "TikTok" in tiktok.json()["detail"]

    fake.errors[VIDEO] = "This video is private, so Snipzo can't import it."
    private = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "true",
            "source_url": f"https://www.youtube.com/watch?v={VIDEO}",
        },
    )
    assert private.status_code == 400
    assert "private" in private.json()["detail"]
    assert fake.downloads == []


@pytest.mark.parametrize(
    "message",
    [
        "This video is age-restricted and can't be imported.",
        "This video is members-only, so Snipzo can't import it.",
        "This livestream is still in progress. Import it after it ends.",
    ],
)
def test_restricted_videos_rejected_before_download(
    client: TestClient, message: str
) -> None:
    fake = _downloader()
    fake.errors[VIDEO] = message
    headers = register(client)
    response = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "true",
            "source_url": f"https://www.youtube.com/watch?v={VIDEO}",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == message
    assert fake.downloads == []


def test_plan_duration_is_enforced_before_download(client: TestClient) -> None:
    fake = _downloader()
    fake.by_id[VIDEO] = YoutubeVideoInfo(
        video_id=VIDEO,
        title="Very long talk",
        duration=31 * 60,
        thumbnail_url="https://i.ytimg.com/vi/dQw4w9wg9cQ/hqdefault.jpg",
        url=f"https://www.youtube.com/watch?v={VIDEO}",
    )
    headers = register(client)
    response = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "true",
            "source_url": f"https://www.youtube.com/watch?v={VIDEO}",
        },
    )
    assert response.status_code == 402, response.text
    detail = response.json()["detail"]
    assert "min left" in detail or "minutes" in detail
    assert fake.downloads == []


def test_disabled_downloader_rejects_youtube_urls(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from snipzo.api.settings import get_api_settings

    monkeypatch.setenv("SNIPZO_YOUTUBE_IMPORT_DOWNLOADER", "disabled")
    get_api_settings.cache_clear()
    headers = register(client)
    response = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "true",
            "source_url": f"https://www.youtube.com/watch?v={VIDEO}",
        },
    )
    assert response.status_code == 400
    assert "turned off" in response.json()["detail"]
    get_api_settings.cache_clear()
