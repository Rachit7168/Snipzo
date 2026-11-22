from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from snipzo.edit import CaptionLine, captions_to_words  # noqa: E402
from tests.api_support import make_client, register, upload  # noqa: E402


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from make_client(tmp_path, monkeypatch)


def test_captions_to_words_spreads_evenly() -> None:
    words = captions_to_words(
        [
            CaptionLine(start=1.0, end=2.0, text="hello brave world"),
            CaptionLine(start=2.0, end=2.5, text="   "),
        ]
    )
    assert [word.text for word in words] == ["hello", "brave", "world"]
    assert words[0].start == pytest.approx(1.0)
    assert words[-1].end == pytest.approx(2.0)


def _project_with_clip(
    client: TestClient, factory: Callable[..., Path]
) -> tuple[dict[str, str], str, dict[str, object]]:
    video = factory(name="talk.mp4", duration=6.0)
    headers = register(client)
    created = upload(client, headers, video)
    project_id = str(created["id"])
    detail = client.get(f"/projects/{project_id}", headers=headers).json()
    assert detail["status"] == "complete", detail
    return headers, project_id, detail["clips"][0]


def test_editor_state_and_caption_edit_rerender(
    client: TestClient, sample_video_factory: Callable[..., Path]
) -> None:
    headers, project_id, clip = _project_with_clip(client, sample_video_factory)
    clip_id = clip["clip_id"]

    state = client.get(
        f"/projects/{project_id}/clips/{clip_id}/editor", headers=headers
    )
    assert state.status_code == 200, state.text
    body = state.json()
    assert body["captions"], body
    assert body["captions_edited"] is False
    assert "bold-yellow" in body["styles"]
    assert body["source_url"]
    assert body["source_duration"] == pytest.approx(6.0, abs=0.2)
    source = client.get(body["source_url"].replace("http://testserver", ""))
    assert source.status_code == 200

    captions = body["captions"]
    captions[0]["text"] = "Edited caption text"
    response = client.patch(
        f"/projects/{project_id}/clips/{clip_id}",
        headers=headers,
        json={
            "captions": captions,
            "title": "A much better title",
            "hook_title": "Watch this first",
            "hashtags": ["focus", "#Productivity"],
            "style_id": "clean-white",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["trimmed"] is False
    assert result["job"]["status"] == "succeeded", result["job"]
    assert result["clip"]["title"] == "A much better title"
    assert result["clip"]["hook_title"] == "Watch this first"
    assert result["clip"]["hashtags"] == ["#Shorts", "#focus", "#Productivity"]
    assert result["clip"]["style_id"] == "clean-white"
    assert result["clip"]["render_version"] == 2

    again = client.get(
        f"/projects/{project_id}/clips/{clip_id}/editor", headers=headers
    ).json()
    assert again["captions_edited"] is True
    assert again["captions"][0]["text"] == "Edited caption text"
    assert again["job"]["kind"] == "rerender"


def test_trim_regenerates_captions_and_validates(
    client: TestClient, sample_video_factory: Callable[..., Path]
) -> None:
    headers, project_id, clip = _project_with_clip(client, sample_video_factory)
    clip_id = clip["clip_id"]
    url = f"/projects/{project_id}/clips/{clip_id}"

    too_short = client.patch(url, headers=headers, json={"start": 1.0, "end": 2.0})
    assert too_short.status_code == 422
    past_end = client.patch(url, headers=headers, json={"start": 1.0, "end": 60.0})
    assert past_end.status_code == 422

    response = client.patch(url, headers=headers, json={"start": 0.5, "end": 4.5})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["trimmed"] is True
    assert result["clip"]["start"] == pytest.approx(0.5)
    assert result["clip"]["end"] == pytest.approx(4.5)
    assert result["job"]["status"] == "succeeded"
    download = client.get(
        result["clip"]["download_url"].replace("http://testserver", "")
    )
    assert download.status_code == 200

    other = register(client, "b@example.com")
    assert client.patch(url, headers=other, json={"title": "x"}).status_code == 404


def test_edit_without_rerender_only_saves(
    client: TestClient, sample_video_factory: Callable[..., Path]
) -> None:
    headers, project_id, clip = _project_with_clip(client, sample_video_factory)
    response = client.patch(
        f"/projects/{project_id}/clips/{clip['clip_id']}",
        headers=headers,
        json={"title": "Only metadata", "rerender": False},
    )
    assert response.status_code == 200
    assert response.json()["job"] is None
    assert response.json()["clip"]["render_version"] == 1
