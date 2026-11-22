"""Billing endpoints: plans, usage, Stripe Checkout/Portal, and the webhook."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from snipzo.api import billing
from snipzo.api.deps import Config, CurrentUser, DbSession
from snipzo.api.tables import BillingEvent, User
from snipzo.errors import SnipzoError

router = APIRouter(prefix="/billing", tags=["billing"])


class PlanOut(BaseModel):
    id: str
    name: str
    price_usd: int
    videos_per_month: int
    minutes_per_month: int
    max_resolution: str
    watermark: bool
    features: list[str]
    purchasable: bool


class UsageOut(BaseModel):
    plan: PlanOut
    videos_used: int
    minutes_used: float
    period_start: datetime
    billing_configured: bool
    has_subscription: bool


class CheckoutIn(BaseModel):
    plan: Literal["creator", "pro"]


def _plan_out(plan: billing.Plan, settings: Any) -> PlanOut:
    width = int(plan.max_height * 9 / 16)
    return PlanOut(
        id=plan.id,
        name=plan.name,
        price_usd=plan.price_usd,
        videos_per_month=plan.videos_per_month,
        minutes_per_month=plan.minutes_per_month,
        max_resolution=f"{width}x{plan.max_height}",
        watermark=plan.watermark,
        features=list(plan.features),
        purchasable=bool(billing.price_for_plan(settings, plan.id))
        and billing.stripe_configured(settings),
    )


@router.get("/plans", response_model=list[PlanOut])
def list_plans(settings: Config) -> list[PlanOut]:
    return [_plan_out(plan, settings) for plan in billing.plans(settings).values()]


@router.get("/me", response_model=UsageOut)
def my_usage(db: DbSession, user: CurrentUser, settings: Config) -> UsageOut:
    usage = billing.usage_for(db, user.id)
    return UsageOut(
        plan=_plan_out(billing.plan_for(user, settings), settings),
        videos_used=usage.videos,
        minutes_used=round(usage.minutes, 2),
        period_start=usage.period_start,
        billing_configured=billing.stripe_configured(settings),
        has_subscription=bool(user.stripe_subscription_id),
    )


@router.post("/checkout")
def checkout(body: CheckoutIn, user: CurrentUser, settings: Config) -> dict[str, str]:
    try:
        return {"url": billing.create_checkout_session(settings, user, body.plan)}
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post("/portal")
def portal(user: CurrentUser, settings: Config) -> dict[str, str]:
    try:
        return {"url": billing.create_portal_session(settings, user)}
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


def _user_from(db: DbSession, obj: dict[str, Any]) -> User | None:
    metadata = obj.get("metadata") or {}
    user_id = metadata.get("user_id") or obj.get("client_reference_id")
    if user_id:
        user = db.get(User, str(user_id))
        if user is not None:
            return user
    customer = obj.get("customer")
    if customer:
        return db.scalar(select(User).where(User.stripe_customer_id == str(customer)))
    return None


@router.post("/webhook")
async def stripe_webhook(
    request: Request, db: DbSession, settings: Config
) -> dict[str, str]:
    """Apply subscription changes from Stripe (signature-verified, idempotent)."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook not configured."
        )
    payload = await request.body()
    try:
        event = billing.verify_webhook(
            payload,
            request.headers.get("stripe-signature"),
            settings.stripe_webhook_secret,
        )
    except SnipzoError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    event_id = str(event.get("id", ""))
    if event_id and db.get(BillingEvent, event_id) is not None:
        return {"status": "duplicate"}
    kind = str(event.get("type", ""))
    obj = (event.get("data") or {}).get("object") or {}
    user = _user_from(db, obj)
    result = "ignored"
    if user is not None:
        if kind == "checkout.session.completed":
            plan_id = (obj.get("metadata") or {}).get("plan")
            if plan_id in billing.plans(settings):
                user.plan = str(plan_id)
            if obj.get("customer"):
                user.stripe_customer_id = str(obj["customer"])
            if obj.get("subscription"):
                user.stripe_subscription_id = str(obj["subscription"])
            result = "upgraded"
        elif kind in {"customer.subscription.created", "customer.subscription.updated"}:
            items = (obj.get("items") or {}).get("data") or []
            price = (items[0].get("price") or {}).get("id") if items else None
            plan_id = billing.plan_for_price(settings, price) or (
                obj.get("metadata") or {}
            ).get("plan")
            if obj.get("status") in {"active", "trialing"} and plan_id:
                user.plan = str(plan_id)
                user.stripe_subscription_id = str(obj.get("id") or "") or None
                result = "updated"
            elif obj.get("status") in {"canceled", "unpaid", "incomplete_expired"}:
                user.plan = "free"
                user.stripe_subscription_id = None
                result = "downgraded"
        elif kind == "customer.subscription.deleted":
            user.plan = "free"
            user.stripe_subscription_id = None
            result = "downgraded"
    if event_id:
        db.add(BillingEvent(id=event_id, type=kind, user_id=user.id if user else None))
    return {"status": result}
