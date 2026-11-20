"""Application settings loaded from the environment and an optional `.env` file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Snipzo pipeline."""

    model_config = SettingsConfigDict(
        env_prefix="SNIPZO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    work_dir: Path = Field(
        default=Path("./data"),
        description="Directory for project files, transcripts, clips, and renders.",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="API key for Claude (clip selection and metadata generation).",
    )
    whisper_model: str = Field(
        default="base",
        description="faster-whisper model size used for transcription.",
    )
    transcriber: Literal["faster-whisper", "deepgram"] = Field(
        default="faster-whisper",
        description="Transcription backend.",
    )
    deepgram_api_key: str | None = Field(
        default=None,
        description="API key for the optional Deepgram transcription backend.",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
