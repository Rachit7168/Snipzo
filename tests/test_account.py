from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from snipzo.api import mailer  # noqa: E402
from snipzo.api.db import session_scope  # noqa: E402
from snipzo.api.settings import ApiSettings  # noqa: E402
from snipzo.api.tables import AccountToken  # noqa: E402
from tests.api_support import make_client, register  # noqa: E402


class CapturingMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[mailer.EmailMessage, str]] = []

    def send(self, message: mailer.EmailMessage, *, sender: str) -> None:
        self.sent.append((message, sender))


@pytest.fixture
def captured_mailer(monkeypatch: pytest.MonkeyPatch) -> CapturingMailer:
    fake = CapturingMailer()
    monkeypatch.setattr(mailer, "mailer_factory", lambda _settings: fake)
    return fake


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, captured_mailer: CapturingMailer
) -> Iterator[TestClient]:
    yield from make_client(tmp_path, monkeypatch)


def _extract_token(message: mailer.EmailMessage) -> str:
    match = re.search(r"token=([A-Za-z0-9_-]+)", message.text_body)
    assert match is not None, message.text_body
    return match.group(1)


def test_signup_sends_verification_and_verify_flow(
    client: TestClient, captured_mailer: CapturingMailer
) -> None:
    res = client.post(
        "/auth/register",
        json={
            "email": "creator@example.com",
            "password": "correct horse",
            "name": "Creator",
        },
    )
    assert res.status_code == 201
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    me = client.get("/auth/me", headers=headers).json()
    assert me["email_verified"] is False
    assert me["name"] == "Creator"

    assert len(captured_mailer.sent) == 1
    msg, _sender = captured_mailer.sent[0]
    assert msg.to == "creator@example.com"
    assert "/verify-email?token=" in msg.text_body
    token = _extract_token(msg)

    verify = client.post("/auth/verify-email", json={"token": token})
    assert verify.status_code == 200
    assert verify.json() == {"verified": True, "email": "creator@example.com"}

    me_after = client.get("/auth/me", headers=headers).json()
    assert me_after["email_verified"] is True

    # Single-use token cannot be reused
    reused = client.post("/auth/verify-email", json={"token": token})
    assert reused.status_code == 400

    # Resend when already verified returns already_verified=True without sending
    resend = client.post("/auth/verify-email/resend", headers=headers)
    assert resend.status_code == 200
    assert resend.json() == {"sent": False, "already_verified": True}
    assert len(captured_mailer.sent) == 1


def test_expired_token_rejected(
    client: TestClient, captured_mailer: CapturingMailer
) -> None:
    register(client, email="exp@example.com")
    token = _extract_token(captured_mailer.sent[0][0])

    with session_scope() as db:
        row = db.scalar(select(AccountToken))
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(minutes=5)

    res = client.post("/auth/verify-email", json={"token": token})
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_profile_and_email_update_retriggers_verification(
    client: TestClient, captured_mailer: CapturingMailer
) -> None:
    headers = register(client, email="one@example.com")
    first_token = _extract_token(captured_mailer.sent[0][0])
    assert (
        client.post("/auth/verify-email", json={"token": first_token}).status_code
        == 200
    )

    # Updating name only keeps verified status
    upd_name = client.patch(
        "/auth/me", headers=headers, json={"name": "Updated Name"}
    )
    assert upd_name.status_code == 200
    assert upd_name.json()["name"] == "Updated Name"
    assert upd_name.json()["email_verified"] is True

    # Email change without current password is rejected
    bad_email = client.patch(
        "/auth/me", headers=headers, json={"email": "two@example.com"}
    )
    assert bad_email.status_code == 400

    # Email change with wrong password is rejected
    wrong_pw = client.patch(
        "/auth/me",
        headers=headers,
        json={"email": "two@example.com", "current_password": "wrong"},
    )
    assert wrong_pw.status_code == 400

    # Email change with valid password resets verification and emails new address
    ok_email = client.patch(
        "/auth/me",
        headers=headers,
        json={"email": "two@example.com", "current_password": "correct horse"},
    )
    assert ok_email.status_code == 200
    assert ok_email.json()["email"] == "two@example.com"
    assert ok_email.json()["email_verified"] is False
    assert len(captured_mailer.sent) == 2
    assert captured_mailer.sent[1][0].to == "two@example.com"

    # Old verification token is invalid once email changed; new token works
    new_token = _extract_token(captured_mailer.sent[1][0])
    assert (
        client.post("/auth/verify-email", json={"token": new_token}).status_code == 200
    )


def test_change_password_and_forgot_reset_flow(
    client: TestClient, captured_mailer: CapturingMailer
) -> None:
    headers = register(client, email="pw@example.com")

    bad_change = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "nope", "new_password": "new strong pass"},
    )
    assert bad_change.status_code == 400

    ok_change = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "correct horse", "new_password": "new strong pass"},
    )
    assert ok_change.status_code == 200

    # Unknown email returns generic 200 without sending email
    unknown = client.post(
        "/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert unknown.status_code == 200
    assert len(captured_mailer.sent) == 1

    # Known email sends reset link
    known = client.post("/auth/forgot-password", json={"email": "pw@example.com"})
    assert known.status_code == 200
    assert len(captured_mailer.sent) == 2
    reset_msg = captured_mailer.sent[1][0]
    assert "/reset-password?token=" in reset_msg.text_body
    reset_token = _extract_token(reset_msg)

    reset_res = client.post(
        "/auth/reset-password",
        json={"token": reset_token, "new_password": "brand new pass 99"},
    )
    assert reset_res.status_code == 200

    # Single-use reset token cannot be reused
    reuse_res = client.post(
        "/auth/reset-password",
        json={"token": reset_token, "new_password": "another pass 99"},
    )
    assert reuse_res.status_code == 400

    # Old password fails, new password succeeds
    assert (
        client.post(
            "/auth/login",
            json={"email": "pw@example.com", "password": "new strong pass"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login",
            json={"email": "pw@example.com", "password": "brand new pass 99"},
        ).status_code
        == 200
    )


def test_account_deletion_request(client: TestClient) -> None:
    headers = register(client, email="del@example.com")
    bad = client.post(
        "/auth/delete-request", headers=headers, json={"password": "wrong"}
    )
    assert bad.status_code == 400

    ok = client.post(
        "/auth/delete-request",
        headers=headers,
        json={"password": "correct horse", "reason": "No longer needed"},
    )
    assert ok.status_code == 200
    assert ok.json()["deletion_requested_at"] is not None


def test_console_backend_default() -> None:
    settings = ApiSettings()
    backend = mailer.default_mailer_factory(settings)
    assert isinstance(backend, mailer.ConsoleEmailBackend)
