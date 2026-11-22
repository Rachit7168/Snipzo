"""Transactional email abstraction with console, SMTP, and Resend backends."""

from __future__ import annotations

import logging
import smtplib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage as MimeEmailMessage
from typing import Protocol

import httpx

from snipzo.api.settings import ApiSettings
from snipzo.errors import SnipzoError

log = logging.getLogger(__name__)
RESEND_API_URL = "https://api.resend.com/emails"


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str | None = None


class EmailBackend(Protocol):
    def send(self, message: EmailMessage, *, sender: str) -> None: ...


class ConsoleEmailBackend:
    """Development/staging backend that logs outbound emails without sending."""

    def send(self, message: EmailMessage, *, sender: str) -> None:
        log.info(
            "Email [console] from=%s to=%s subject=%r body=%s",
            sender,
            message.to,
            message.subject,
            message.text_body,
        )
        if not logging.getLogger().handlers and not log.handlers:
            print(
                f"Email [console] from={sender} to={message.to} "
                f"subject={message.subject!r}\n{message.text_body}",
                file=sys.stderr,
                flush=True,
            )


class SmtpEmailBackend:
    """SMTP email sender configured via SNIPZO_SMTP_* env settings."""

    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings

    def send(self, message: EmailMessage, *, sender: str) -> None:
        if not self.settings.smtp_host:
            raise SnipzoError("Email delivery is not configured on this server.")
        mime = MimeEmailMessage()
        mime["From"] = sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text_body)
        if message.html_body:
            mime.add_alternative(message.html_body, subtype="html")
        with smtplib.SMTP(
            self.settings.smtp_host, self.settings.smtp_port, timeout=15
        ) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_user and self.settings.smtp_password:
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(mime)


class ResendEmailBackend:
    """Resend HTTPS email sender configured via SNIPZO_RESEND_API_KEY."""

    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings

    def send(self, message: EmailMessage, *, sender: str) -> None:
        if not self.settings.resend_api_key:
            raise SnipzoError("Email delivery is not configured on this server.")
        payload: dict[str, object] = {
            "from": sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text_body,
        }
        if message.html_body:
            payload["html"] = message.html_body
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
                json=payload,
            )
        if resp.status_code >= 400:
            raise SnipzoError("Could not send email right now. Please try again.")


def default_mailer_factory(settings: ApiSettings) -> EmailBackend:
    if settings.email_backend == "smtp":
        return SmtpEmailBackend(settings)
    if settings.email_backend == "resend":
        return ResendEmailBackend(settings)
    return ConsoleEmailBackend()


# Tests swap this factory to capture emails without touching network/SMTP.
mailer_factory: Callable[[ApiSettings], EmailBackend] = default_mailer_factory


def send_email(message: EmailMessage, settings: ApiSettings) -> None:
    backend = mailer_factory(settings)
    backend.send(message, sender=settings.email_from)


def send_verification_email(
    email: str, verify_url: str, settings: ApiSettings
) -> None:
    send_email(
        EmailMessage(
            to=email,
            subject="Verify your Snipzo email address",
            text_body=(
                "Welcome to Snipzo!\n\n"
                "Confirm your email address by opening this link "
                "(expires in 24 hours):\n"
                f"{verify_url}\n\n"
                "If you did not create a Snipzo account, "
                "you can safely ignore this email."
            ),
            html_body=(
                "<p>Welcome to <strong>Snipzo</strong>!</p>"
                "<p>Confirm your email address by clicking the link below "
                "(expires in 24 hours):</p>"
                f'<p><a href="{verify_url}">Verify my email</a></p>'
                "<p>If you did not create a Snipzo account, "
                "you can safely ignore this email.</p>"
            ),
        ),
        settings,
    )


def send_password_reset_email(
    email: str, reset_url: str, settings: ApiSettings
) -> None:
    send_email(
        EmailMessage(
            to=email,
            subject="Reset your Snipzo password",
            text_body=(
                "We received a request to reset your Snipzo password.\n\n"
                "Choose a new password using this link (expires in 1 hour):\n"
                f"{reset_url}\n\n"
                "If you did not request a password reset, "
                "you can safely ignore this email."
            ),
            html_body=(
                "<p>We received a request to reset your "
                "<strong>Snipzo</strong> password.</p>"
                "<p>Choose a new password using the link below "
                "(expires in 1 hour):</p>"
                f'<p><a href="{reset_url}">Reset my password</a></p>'
                "<p>If you did not request a password reset, "
                "you can safely ignore this email.</p>"
            ),
        ),
        settings,
    )
