from pathlib import Path

import pytest

from snipzo.config import Settings


def test_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Avoid picking up a developer .env or leftover env vars.
    for key in (
        "SNIPZO_WORK_DIR",
        "SNIPZO_ANTHROPIC_API_KEY",
        "SNIPZO_WHISPER_MODEL",
        "SNIPZO_LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)
    assert settings.work_dir == Path("./data")
    assert settings.anthropic_api_key is None
    assert settings.whisper_model == "large-v3"
    assert settings.log_level == "INFO"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work_dir = tmp_path / "projects"
    monkeypatch.setenv("SNIPZO_WORK_DIR", str(work_dir))
    monkeypatch.setenv("SNIPZO_WHISPER_MODEL", "tiny")
    monkeypatch.setenv("SNIPZO_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SNIPZO_ANTHROPIC_API_KEY", "test-key")

    settings = Settings(_env_file=None)
    assert settings.work_dir == work_dir
    assert settings.whisper_model == "tiny"
    assert settings.log_level == "DEBUG"
    assert settings.anthropic_api_key == "test-key"
