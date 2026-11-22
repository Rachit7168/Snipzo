"""Run Alembic migrations programmatically (used by `snipzo db upgrade`)."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from snipzo.api.settings import get_api_settings


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "snipzo.api:migrations")
    url = database_url or get_api_settings().database_url
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade(database_url: str | None = None, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)
