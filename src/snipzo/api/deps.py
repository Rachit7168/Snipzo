"""FastAPI dependencies: database sessions and the signed-in user."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from snipzo.api.db import session_factory
from snipzo.api.security import unsign
from snipzo.api.settings import ApiSettings, get_api_settings
from snipzo.api.tables import User


def get_db() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]
Config = Annotated[ApiSettings, Depends(get_api_settings)]


def current_user(
    db: DbSession,
    settings: Config,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")
    payload = unsign(authorization.split(" ", 1)[1].strip(), settings.secret_key)
    if not payload or payload.get("typ") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")
    user = db.get(User, str(payload.get("sub")))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
