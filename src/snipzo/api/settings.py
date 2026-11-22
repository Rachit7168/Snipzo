"""Settings for the API, workers, database, and blob storage."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Configuration for the hosted service (all values come from `SNIPZO_*`)."""

    model_config = SettingsConfigDict(
        env_prefix="SNIPZO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./data/snipzo.db",
        description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pw@host/db.",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker and result backend.",
    )
    celery_eager: bool = Field(
        default=False,
        description="Run Celery tasks inline (tests and single-process demos).",
    )
    secret_key: str = Field(
        default="dev-insecure-change-me",
        description="Signs API tokens and download links. Set a long random value.",
    )
    token_ttl_seconds: int = Field(default=7 * 24 * 3600)
    download_ttl_seconds: int = Field(default=6 * 3600)
    public_api_url: str = Field(
        default="http://localhost:8000",
        description="Base URL used when building download links.",
    )
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated origins allowed to call the API.",
    )
    storage_backend: Literal["local", "s3"] = Field(default="local")
    storage_dir: Path = Field(
        default=Path("./data/blobs"),
        description="Root for the local blob store.",
    )
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = Field(
        default=None,
        description="Set for Cloudflare R2 / MinIO, e.g. https://<acct>.r2.cloudflarestorage.com.",
    )
    s3_region: str = "auto"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    source_retention_days: int = Field(
        default=14,
        ge=1,
        le=30,
        description="Delete uploaded source videos after this many days.",
    )
    max_upload_mb: int = Field(default=2048)
    url_import_enabled: bool = Field(
        default=True,
        description="Allow importing direct video file URLs (not YouTube pages).",
    )

    web_app_url: str = Field(
        default="http://localhost:3000",
        description="Where OAuth callbacks send the browser afterwards.",
    )
    google_client_id: str | None = Field(
        default=None, description="Google OAuth client ID (YouTube Data API)."
    )
    google_client_secret: str | None = None
    google_redirect_uri: str = Field(
        default="http://localhost:8000/youtube/callback",
        description="Authorized redirect URI registered in Google Cloud.",
    )
    token_encryption_key: str | None = Field(
        default=None,
        description="Fernet key for OAuth tokens at rest (derived from "
        "SNIPZO_SECRET_KEY when unset).",
    )
    youtube_import_downloader: Literal["disabled", "yt-dlp"] = Field(
        default="disabled",
        description="How to fetch media for owned YouTube imports.",
    )

    billing_enforced: bool = Field(
        default=True,
        description="Enforce monthly video/minute quotas and free-tier watermarking.",
    )
    free_videos_per_month: int = Field(default=3, ge=1)
    free_minutes_per_month: int = Field(default=30, ge=1)
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_creator: str | None = None
    stripe_price_pro: str | None = None

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_api_settings() -> ApiSettings:
    """Return cached API settings."""
    return ApiSettings()
