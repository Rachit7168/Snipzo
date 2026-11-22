from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from tests.api_support import make_client, register, upload  # noqa: E402


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from make_client(tmp_path, monkeypatch)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_login_and_me(client: TestClient) -> None:
    headers = register(client)
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "a@example.com"
    assert me.json()["plan"] == "free"

    dup = client.post(
        "/auth/register", json={"email": "A@example.com", "password": "another one"}
    )
    assert dup.status_code == 409

    bad = client.post(
        "/auth/login", json={"email": "a@example.com", "password": "wrong password"}
    )
    assert bad.status_code == 401
    good = client.post(
        "/auth/login", json={"email": "a@example.com", "password": "correct horse"}
    )
    assert good.status_code == 200
    assert good.json()["access_token"]


def test_projects_require_auth(client: TestClient) -> None:
    assert client.get("/projects").status_code == 401
    assert (
        client.get("/projects", headers={"Authorization": "Bearer nope"}).status_code
        == 401
    )


def test_upload_requires_rights_confirmation(
    client: TestClient, sample_video: Path
) -> None:
    headers = register(client)
    with sample_video.open("rb") as handle:
        response = client.post(
            "/projects",
            headers=headers,
            data={"rights_confirmed": "false"},
            files={"file": ("talk.mp4", handle, "video/mp4")},
        )
    assert response.status_code == 400
    assert "rights" in response.json()["detail"]


def test_youtube_links_are_rejected(client: TestClient) -> None:
    headers = register(client)
    response = client.post(
        "/projects",
        headers=headers,
        data={
            "rights_confirmed": "true",
            "source_url": "https://www.youtube.com/watch?v=abc",
        },
    )
    assert response.status_code == 400
    assert "YouTube" in response.json()["detail"]


def test_upload_runs_pipeline_through_workers(
    client: TestClient,
    sample_video_factory: Callable[..., Path],
) -> None:
    video = sample_video_factory(name="talk.mp4", duration=4.0)
    headers = register(client)
    created = upload(client, headers, video, title="My talk")
    project_id = str(created["id"])

    detail = client.get(f"/projects/{project_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "complete", body
    assert body["job"]["status"] == "succeeded"
    assert body["job"]["progress"] == 1.0
    assert body["title"] == "My talk"
    assert body["duration_seconds"] == pytest.approx(4.0, abs=0.2)
    assert len(body["clips"]) == 1
    clip = body["clips"][0]
    assert clip["render_version"] == 1
    assert clip["reason"]
    assert "#Shorts" in clip["hashtags"]

    download = client.get(clip["download_url"].replace("http://testserver", ""))
    assert download.status_code == 200
    assert download.headers["content-type"] == "video/mp4"
    assert len(download.content) > 1000

    listing = client.get("/projects", headers=headers).json()
    assert [item["id"] for item in listing] == [project_id]

    other = register(client, "b@example.com")
    assert client.get(f"/projects/{project_id}", headers=other).status_code == 404


def test_failed_job_is_reported(
    client: TestClient,
    tmp_path: Path,
) -> None:
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video at all")
    headers = register(client)
    created = upload(client, headers, broken)
    detail = client.get(f"/projects/{created['id']}", headers=headers).json()
    assert detail["status"] == "failed"
    assert detail["job"]["status"] == "failed"
    assert detail["error"]


def test_download_link_rejects_tampering(client: TestClient) -> None:
    assert client.get("/files/abc.def").status_code == 403


def test_cleanup_sources_deletes_old_uploads(
    client: TestClient, sample_video_factory: Callable[..., Path]
) -> None:
    from snipzo.api.blobstore import get_blob_store
    from snipzo.api.jobs import cleanup_sources
    from snipzo.api.settings import get_api_settings

    video = sample_video_factory(name="talk.mp4", duration=4.0)
    headers = register(client)
    created = upload(client, headers, video)
    store = get_blob_store(get_api_settings())
    sources = store.list("sources/")
    assert len(sources) == 1

    assert cleanup_sources(now=datetime.now(UTC)) == []
    cleaned = cleanup_sources(now=datetime.now(UTC) + timedelta(days=30))
    assert cleaned == [created["id"]]
    assert store.list("sources/") == []
    detail = client.get(f"/projects/{created['id']}", headers=headers).json()
    assert detail["source_available"] is False


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_file(
        self, filename: str, bucket: str, key: str, ExtraArgs: Any = None
    ) -> None:
        del bucket, ExtraArgs
        self.objects[key] = Path(filename).read_bytes()

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        del bucket
        Path(filename).write_bytes(self.objects[key])

    def head_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        del Bucket
        if Key not in self.objects:
            raise KeyError(Key)
        return {}

    def delete_object(self, Bucket: str, Key: str) -> None:
        del Bucket
        self.objects.pop(Key, None)

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        prefix = kwargs["Prefix"]
        return {
            "Contents": [
                {"Key": key, "Size": len(data), "LastModified": datetime.now(UTC)}
                for key, data in self.objects.items()
                if key.startswith(prefix)
            ],
            "IsTruncated": False,
        }

    def generate_presigned_url(
        self, op: str, Params: dict[str, str], ExpiresIn: int
    ) -> str:
        return f"https://r2.example/{Params['Bucket']}/{Params['Key']}?op={op}&e={ExpiresIn}"


def test_s3_blob_store_roundtrip(tmp_path: Path) -> None:
    from snipzo.api.blobstore import S3BlobStore

    fake = FakeS3()
    store = S3BlobStore("snipzo", fake)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video")
    store.put_file("renders/p/a.mp4", src, content_type="video/mp4")
    assert store.exists("renders/p/a.mp4")
    assert [item.key for item in store.list("renders/")] == ["renders/p/a.mp4"]
    out = store.get_file("renders/p/a.mp4", tmp_path / "out.mp4")
    assert out.read_bytes() == b"video"
    url = store.presigned_url("renders/p/a.mp4", 60)
    assert url is not None and url.startswith("https://r2.example/snipzo/")
    store.delete("renders/p/a.mp4")
    assert not store.exists("renders/p/a.mp4")


def test_local_blob_store_rejects_traversal(tmp_path: Path) -> None:
    from snipzo.api.blobstore import LocalBlobStore
    from snipzo.errors import SnipzoError

    store = LocalBlobStore(tmp_path / "blobs")
    with pytest.raises(SnipzoError):
        store.exists("../../etc/passwd")


def test_token_signing() -> None:
    from snipzo.api.security import hash_password, sign, unsign, verify_password

    token = sign({"sub": "u1"}, "s", 60)
    assert unsign(token, "s") is not None
    assert unsign(token, "other") is None
    assert unsign(sign({"sub": "u1"}, "s", -1), "s") is None
    stored = hash_password("hunter22")
    assert verify_password("hunter22", stored)
    assert not verify_password("nope", stored)


def test_celery_routes_split_gpu_and_cpu() -> None:
    from snipzo.api.worker import celery_app, configure_celery

    configure_celery()
    routes = celery_app.conf.task_routes
    assert routes["snipzo.ingest_transcribe"]["queue"] == "gpu"
    assert routes["snipzo.highlights_render"]["queue"] == "cpu"
