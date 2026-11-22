"""Plans, usage metering, plan enforcement, watermarking, and Stripe helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from snipzo.api.settings import ApiSettings
from snipzo.api.tables import ProjectRow, UsageEvent, User
from snipzo.errors import SnipzoError
from snipzo.media import run_ffmpeg

STRIPE_API = "https://api.stripe.com/v1"

# Tests swap this for an httpx.Client backed by httpx.MockTransport.
stripe_http_factory: Callable[[], httpx.Client] = lambda: httpx.Client(  # noqa: E731
    timeout=30.0
)


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_usd: int
    videos_per_month: int
    minutes_per_month: int
    max_height: int
    watermark: bool
    features: tuple[str, ...]


def plans(settings: ApiSettings) -> dict[str, Plan]:
    return {
        "free": Plan(
            id="free",
            name="Free",
            price_usd=0,
            videos_per_month=settings.free_videos_per_month,
            minutes_per_month=settings.free_minutes_per_month,
            max_height=1280,
            watermark=True,
            features=("720p exports", "Snipzo watermark"),
        ),
        "creator": Plan(
            id="creator",
            name="Creator",
            price_usd=19,
            videos_per_month=30,
            minutes_per_month=600,
            max_height=1920,
            watermark=False,
            features=(
                "1080p exports",
                "No watermark",
                "Clip editor",
                "YouTube publishing",
            ),
        ),
        "pro": Plan(
            id="pro",
            name="Pro",
            price_usd=49,
            videos_per_month=100,
            minutes_per_month=3000,
            max_height=1920,
            watermark=False,
            features=("Everything in Creator", "Higher limits", "Priority processing"),
        ),
    }


def plan_for(user: User, settings: ApiSettings) -> Plan:
    table = plans(settings)
    return table.get(user.plan, table["free"])


def month_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class Usage:
    videos: int
    minutes: float
    period_start: datetime


def usage_for(session: Session, user_id: str, now: datetime | None = None) -> Usage:
    """Month-to-date usage: projects started (not failed) and minutes processed."""
    start = month_start(now)
    videos = session.scalar(
        select(func.count())
        .select_from(ProjectRow)
        .where(
            ProjectRow.user_id == user_id,
            ProjectRow.created_at >= start,
            ProjectRow.status != "failed",
        )
    )
    minutes = session.scalar(
        select(func.coalesce(func.sum(UsageEvent.minutes), 0.0)).where(
            UsageEvent.user_id == user_id, UsageEvent.created_at >= start
        )
    )
    return Usage(
        videos=int(videos or 0), minutes=float(minutes or 0.0), period_start=start
    )


def check_can_start_video(session: Session, user: User, settings: ApiSettings) -> None:
    """Raise when the plan's monthly video or minute allowance is used up."""
    if not settings.billing_enforced:
        return
    plan = plan_for(user, settings)
    usage = usage_for(session, user.id)
    if usage.videos >= plan.videos_per_month:
        raise SnipzoError(
            f"Your {plan.name} plan includes {plan.videos_per_month} videos per month. "
            "Upgrade to process more."
        )
    if usage.minutes >= plan.minutes_per_month:
        raise SnipzoError(
            f"You've used your {plan.minutes_per_month} minutes this month. "
            "Upgrade to process more."
        )


def check_minutes(
    session: Session, user: User, settings: ApiSettings, minutes: float
) -> None:
    if not settings.billing_enforced:
        return
    plan = plan_for(user, settings)
    used = usage_for(session, user.id).minutes
    if used + minutes > plan.minutes_per_month + 1e-6:
        remaining = max(0.0, plan.minutes_per_month - used)
        raise SnipzoError(
            f"This video is {minutes:.1f} min but your {plan.name} plan has "
            f"{remaining:.1f} min left this month. Upgrade or use a shorter video."
        )


def record_usage(
    session: Session, user_id: str, project_id: str, minutes: float, kind: str = "video"
) -> None:
    session.add(
        UsageEvent(
            user_id=user_id, project_id=project_id, kind=kind, minutes=round(minutes, 3)
        )
    )


def _font_file() -> str | None:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ):
        if Path(candidate).is_file():
            return candidate
    return None


def apply_plan_to_render(path: Path, plan: Plan) -> None:
    """Downscale to the plan's resolution and add the free-tier watermark."""
    if not plan.watermark and plan.max_height >= 1920:
        return
    height = min(1920, plan.max_height)
    width = int(round(height * 9 / 16 / 2) * 2)
    filters = [f"scale={width}:{height}:flags=lanczos"]
    if plan.watermark:
        font = _font_file()
        font_opt = f"fontfile='{font}':" if font else ""
        filters.append(
            "drawtext="
            f"{font_opt}text='Made with Snipzo':fontsize={max(18, height // 45)}:"
            "fontcolor=white@0.75:borderw=2:bordercolor=black@0.6:"
            "x=w-tw-24:y=h-th-48"
        )
    tmp = path.with_suffix(".plan.mp4")
    run_ffmpeg(
        [
            "-i",
            str(path),
            "-vf",
            ",".join(filters),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(tmp),
        ]
    )
    shutil.move(str(tmp), str(path))


# --- Stripe ---------------------------------------------------------------


def stripe_configured(settings: ApiSettings) -> bool:
    return bool(settings.stripe_secret_key)


def price_for_plan(settings: ApiSettings, plan_id: str) -> str | None:
    return {
        "creator": settings.stripe_price_creator,
        "pro": settings.stripe_price_pro,
    }.get(plan_id)


def plan_for_price(settings: ApiSettings, price_id: str | None) -> str | None:
    for plan_id in ("creator", "pro"):
        if price_id and price_for_plan(settings, plan_id) == price_id:
            return plan_id
    return None


def _stripe_post(
    settings: ApiSettings, path: str, data: dict[str, str]
) -> dict[str, Any]:
    if not settings.stripe_secret_key:
        raise SnipzoError("Billing is not configured (set SNIPZO_STRIPE_SECRET_KEY).")
    with stripe_http_factory() as client:
        response = client.post(
            f"{STRIPE_API}/{path}",
            data=data,
            auth=(settings.stripe_secret_key, ""),
        )
    payload = response.json() if response.content else {}
    if response.status_code >= 400:
        message = (
            payload.get("error", {}).get("message")
            if isinstance(payload, dict)
            else None
        )
        raise SnipzoError(f"Stripe error: {message or response.status_code}")
    if not isinstance(payload, dict):
        raise SnipzoError("Unexpected Stripe response.")
    return payload


def create_checkout_session(settings: ApiSettings, user: User, plan_id: str) -> str:
    price = price_for_plan(settings, plan_id)
    if not price:
        raise SnipzoError(f"No Stripe price configured for the {plan_id} plan.")
    base = settings.web_app_url.rstrip("/")
    data = {
        "mode": "subscription",
        "line_items[0][price]": price,
        "line_items[0][quantity]": "1",
        "success_url": f"{base}/billing?checkout=success",
        "cancel_url": f"{base}/billing?checkout=cancelled",
        "client_reference_id": user.id,
        "metadata[user_id]": user.id,
        "metadata[plan]": plan_id,
        "subscription_data[metadata][user_id]": user.id,
        "subscription_data[metadata][plan]": plan_id,
        "allow_promotion_codes": "true",
    }
    if user.stripe_customer_id:
        data["customer"] = user.stripe_customer_id
    else:
        data["customer_email"] = user.email
    session = _stripe_post(settings, "checkout/sessions", data)
    return str(session["url"])


def create_portal_session(settings: ApiSettings, user: User) -> str:
    if not user.stripe_customer_id:
        raise SnipzoError("No subscription to manage yet.")
    session = _stripe_post(
        settings,
        "billing_portal/sessions",
        {
            "customer": user.stripe_customer_id,
            "return_url": f"{settings.web_app_url.rstrip('/')}/billing",
        },
    )
    return str(session["url"])


def verify_webhook(
    payload: bytes, header: str | None, secret: str, tolerance: int = 300
) -> dict[str, Any]:
    """Verify a `Stripe-Signature` header (HMAC-SHA256 over `t.payload`)."""
    if not header:
        raise SnipzoError("Missing Stripe-Signature header.")
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        parts.setdefault(key, []).append(value)
    try:
        timestamp = int(parts["t"][0])
    except (KeyError, ValueError) as exc:
        raise SnipzoError("Malformed Stripe-Signature header.") from exc
    if abs(time.time() - timestamp) > tolerance:
        raise SnipzoError("Stripe webhook timestamp is too old.")
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in parts.get("v1", [])):
        raise SnipzoError("Invalid Stripe webhook signature.")
    event = json.loads(payload)
    if not isinstance(event, dict):
        raise SnipzoError("Invalid webhook payload.")
    return event


def sign_webhook_payload(
    payload: bytes, secret: str, timestamp: int | None = None
) -> str:
    """Build a Stripe-Signature header (used by tests and local tooling)."""
    ts = timestamp or int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256)
    return f"t={ts},v1={sig.hexdigest()}"
