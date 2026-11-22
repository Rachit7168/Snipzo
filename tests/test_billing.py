from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from snipzo.media import probe_video  # noqa: E402
from tests.api_support import make_client, register, upload  # noqa: E402


class FakeStripe:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.calls.append((request.url.path, form))
        if request.url.path.endswith("/checkout/sessions"):
            return httpx.Response(
                200,
                json={"id": "cs_test_1", "url": "https://checkout.stripe.com/pay/cs_1"},
            )
        if request.url.path.endswith("/billing_portal/sessions"):
            return httpx.Response(
                200,
                json={"id": "bps_1", "url": "https://billing.stripe.com/session/bps_1"},
            )
        return httpx.Response(404, json={"error": {"message": "unknown endpoint"}})


@pytest.fixture
def stripe_mock(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    fake = FakeStripe()
    from snipzo.api import billing

    monkeypatch.setattr(
        billing,
        "stripe_http_factory",
        lambda: httpx.Client(transport=httpx.MockTransport(fake.handler)),
    )
    return fake


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stripe_mock: FakeStripe
) -> Iterator[TestClient]:
    monkeypatch.setenv("SNIPZO_STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("SNIPZO_STRIPE_WEBHOOK_SECRET", "whsec_test_123")
    monkeypatch.setenv("SNIPZO_STRIPE_PRICE_CREATOR", "price_creator_19")
    monkeypatch.setenv("SNIPZO_STRIPE_PRICE_PRO", "price_pro_49")
    monkeypatch.setenv("SNIPZO_WEB_APP_URL", "http://web.test")
    yield from make_client(tmp_path, monkeypatch)


def _webhook_post(
    client: TestClient, event: dict[str, Any], secret: str = "whsec_test_123"
) -> Any:
    from snipzo.api.billing import sign_webhook_payload

    raw = json.dumps(event).encode()
    sig = sign_webhook_payload(raw, secret)
    return client.post(
        "/billing/webhook", content=raw, headers={"stripe-signature": sig}
    )


def test_plans_and_usage_metering(
    client: TestClient, sample_video_factory: Callable[..., Path]
) -> None:
    plans = client.get("/billing/plans")
    assert plans.status_code == 200
    by_id = {item["id"]: item for item in plans.json()}
    assert by_id["free"]["max_resolution"] == "720x1280"
    assert by_id["free"]["watermark"] is True
    assert by_id["creator"]["price_usd"] == 19
    assert by_id["creator"]["watermark"] is False
    assert by_id["creator"]["purchasable"] is True

    headers = register(client)
    before = client.get("/billing/me", headers=headers).json()
    assert before["plan"]["id"] == "free"
    assert before["videos_used"] == 0
    assert before["minutes_used"] == 0.0

    video = sample_video_factory(name="talk.mp4", duration=6.0)
    created = upload(client, headers, video)
    detail = client.get(f"/projects/{created['id']}", headers=headers).json()
    assert detail["status"] == "complete"

    # Free tier downscales to 720x1280 and applies watermark.
    dl = client.get(detail["clips"][0]["download_url"].replace("http://testserver", ""))
    assert dl.status_code == 200
    tmp_mp4 = video.parent / "downloaded.mp4"
    tmp_mp4.write_bytes(dl.content)
    info = probe_video(tmp_mp4)
    assert info.width == 720
    assert info.height == 1280

    after = client.get("/billing/me", headers=headers).json()
    assert after["videos_used"] == 1
    assert after["minutes_used"] == pytest.approx(0.1, abs=0.05)


def test_free_tier_video_limit_enforced(
    client: TestClient, sample_video_factory: Callable[..., Path]
) -> None:
    headers = register(client)
    video = sample_video_factory(name="short.mp4", duration=4.0)
    for idx in range(3):
        created = upload(client, headers, video, title=f"v{idx}")
        assert created["status"] == "complete"

    with video.open("rb") as handle:
        fourth = client.post(
            "/projects",
            headers=headers,
            data={"rights_confirmed": "true"},
            files={"file": ("short.mp4", handle, "video/mp4")},
        )
    assert fourth.status_code == 402
    assert "3 videos per month" in fourth.json()["detail"]


def test_free_tier_minutes_limit_enforced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sample_video_factory: Callable[..., Path],
) -> None:
    monkeypatch.setenv("SNIPZO_FREE_MINUTES_PER_MONTH", "1")
    for test_client in make_client(tmp_path, monkeypatch):
        headers = register(test_client)
        # 4s video succeeds (0.07 min)
        ok_vid = sample_video_factory(name="ok.mp4", duration=4.0)
        ok_created = upload(test_client, headers, ok_vid)
        assert ok_created["status"] == "complete"
        # Use up remaining minutes via a usage event, then a 10s upload exceeds 1 min.
        from sqlalchemy import select

        from snipzo.api.billing import record_usage
        from snipzo.api.db import session_scope
        from snipzo.api.tables import User

        with session_scope() as session:
            user = session.scalar(select(User).where(User.email == "a@example.com"))
            assert user is not None
            record_usage(session, user.id, str(ok_created["id"]), 0.88)

        long_vid = sample_video_factory(name="over.mp4", duration=6.0)
        created = upload(test_client, headers, long_vid)
        detail = test_client.get(f"/projects/{created['id']}", headers=headers).json()
        assert detail["status"] == "failed"
        assert "plan has" in detail["error"]


def test_stripe_checkout_webhook_upgrade_and_cancel(
    client: TestClient,
    stripe_mock: FakeStripe,
    sample_video_factory: Callable[..., Path],
) -> None:
    headers = register(client)
    me = client.get("/auth/me", headers=headers).json()

    # Portal fails before subscribing.
    assert client.post("/billing/portal", headers=headers).status_code == 400

    checkout = client.post(
        "/billing/checkout", headers=headers, json={"plan": "creator"}
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["url"] == "https://checkout.stripe.com/pay/cs_1"
    assert stripe_mock.calls[-1][1]["line_items[0][price]"] == "price_creator_19"
    assert stripe_mock.calls[-1][1]["metadata[user_id]"] == me["id"]

    # Bad signature rejected.
    bad = client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert bad.status_code == 400

    # Completed checkout upgrades user to creator.
    evt = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_123",
                "subscription": "sub_123",
                "client_reference_id": me["id"],
                "metadata": {"user_id": me["id"], "plan": "creator"},
            }
        },
    }
    res = _webhook_post(client, evt)
    assert res.status_code == 200
    assert res.json()["status"] == "upgraded"
    # Duplicate webhook event is ignored idempotently.
    assert _webhook_post(client, evt).json()["status"] == "duplicate"

    usage = client.get("/billing/me", headers=headers).json()
    assert usage["plan"]["id"] == "creator"
    assert usage["plan"]["max_resolution"] == "1080x1920"
    assert usage["has_subscription"] is True

    # Portal now returns a Stripe Customer Portal URL.
    portal = client.post("/billing/portal", headers=headers)
    assert portal.status_code == 200
    assert portal.json()["url"] == "https://billing.stripe.com/session/bps_1"

    # Creator exports at 1080x1920 without watermark.
    video = sample_video_factory(name="hd.mp4", duration=4.0)
    created = upload(client, headers, video)
    dl = client.get(
        created["clips"][0]["download_url"].replace("http://testserver", "")
    )
    hd_mp4 = video.parent / "hd_out.mp4"
    hd_mp4.write_bytes(dl.content)
    info = probe_video(hd_mp4)
    assert info.width == 1080
    assert info.height == 1920

    # Subscription deleted downgrades back to free.
    del_evt = {
        "id": "evt_2",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_123", "customer": "cus_123"}},
    }
    res2 = _webhook_post(client, del_evt)
    assert res2.status_code == 200
    assert res2.json()["status"] == "downgraded"
    assert client.get("/billing/me", headers=headers).json()["plan"]["id"] == "free"
