"""Blob storage for sources and renders: S3/R2, with a local-filesystem fallback."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from snipzo.api.settings import ApiSettings
from snipzo.errors import SnipzoError


@dataclass(frozen=True)
class BlobInfo:
    key: str
    size: int
    modified: datetime


class BlobStore(Protocol):
    """Minimal object storage interface used by the API and workers."""

    def put_file(
        self, key: str, path: Path, content_type: str | None = None
    ) -> None: ...

    def get_file(self, key: str, dest: Path) -> Path: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...

    def list(self, prefix: str) -> list[BlobInfo]: ...

    def presigned_url(self, key: str, ttl_seconds: int) -> str | None:
        """Return a direct download URL, or None when the API must stream it."""
        ...

    def local_path(self, key: str) -> Path | None:
        """Return a filesystem path for local stores (None for remote)."""
        ...


class LocalBlobStore:
    """Stores blobs under a directory; used in development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents and path != self.root:
            raise SnipzoError(f"Invalid blob key: {key}")
        return path

    def put_file(self, key: str, path: Path, content_type: str | None = None) -> None:
        del content_type
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != dest:
            shutil.copyfile(path, dest)

    def get_file(self, key: str, dest: Path) -> Path:
        src = self._path(key)
        if not src.is_file():
            raise SnipzoError(f"Blob not found: {key}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src != dest.resolve():
            shutil.copyfile(src, dest)
        return dest

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list(self, prefix: str) -> list[BlobInfo]:
        base = self._path(prefix) if prefix else self.root
        if base.is_file():
            files = [base]
        elif base.is_dir():
            files = [item for item in base.rglob("*") if item.is_file()]
        else:
            files = []
        out: list[BlobInfo] = []
        for item in files:
            stat = item.stat()
            out.append(
                BlobInfo(
                    key=item.relative_to(self.root).as_posix(),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime, UTC),
                )
            )
        return out

    def presigned_url(self, key: str, ttl_seconds: int) -> str | None:
        del key, ttl_seconds
        return None

    def local_path(self, key: str) -> Path | None:
        path = self._path(key)
        return path if path.is_file() else None


class S3BlobStore:
    """S3-compatible storage (AWS S3, Cloudflare R2, MinIO) via boto3."""

    def __init__(self, bucket: str, client: Any) -> None:
        self.bucket = bucket
        self.client = client

    @classmethod
    def from_settings(cls, settings: ApiSettings) -> S3BlobStore:
        if not settings.s3_bucket:
            raise SnipzoError("SNIPZO_S3_BUCKET is required for the s3 backend.")
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - depends on extras
            raise SnipzoError("Install boto3 to use S3/R2 storage.") from exc
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        return cls(settings.s3_bucket, client)

    def put_file(self, key: str, path: Path, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else None
        if extra:
            self.client.upload_file(str(path), self.bucket, key, ExtraArgs=extra)
        else:
            self.client.upload_file(str(path), self.bucket, key)

    def get_file(self, key: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(dest))
        return dest

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception:
            return False
        return True

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def list(self, prefix: str) -> list[BlobInfo]:
        out: list[BlobInfo] = []
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = self.client.list_objects_v2(**kwargs)
            for item in page.get("Contents", []):
                out.append(
                    BlobInfo(
                        key=item["Key"],
                        size=int(item.get("Size", 0)),
                        modified=item["LastModified"],
                    )
                )
            if not page.get("IsTruncated"):
                return out
            token = page.get("NextContinuationToken")

    def presigned_url(self, key: str, ttl_seconds: int) -> str | None:
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )
        return str(url)

    def local_path(self, key: str) -> Path | None:
        del key
        return None


def get_blob_store(settings: ApiSettings) -> BlobStore:
    """Return the configured blob store."""
    if settings.storage_backend == "s3":
        return S3BlobStore.from_settings(settings)
    return LocalBlobStore(settings.storage_dir)


def source_key(project_id: str, filename: str) -> str:
    suffix = Path(filename).suffix.lower() or ".mp4"
    return f"sources/{project_id}/source{suffix}"


def render_key(project_id: str, clip_id: str, version: int = 1) -> str:
    return f"renders/{project_id}/{clip_id}-v{version}.mp4"
