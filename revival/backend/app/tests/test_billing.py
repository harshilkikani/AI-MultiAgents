"""M8 tests: Stripe stub checkout + webhook + trial/payment gate."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")

    import sys
    for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        sys.modules.pop(mod, None)

    from app.db import init_db
    from app.main import app as fresh_app
    init_db()
    return fresh_app


@pytest.mark.asyncio
async def test_checkout_returns_demo_url(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "bill", "vertical": "septic"})
        cid = r.json()["id"]
        r = await c.post(f"/api/campaigns/{cid}/checkout?plan=one_shot")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "demo"
        assert body["url"].startswith("/demo/checkout")


@pytest.mark.asyncio
async def test_demo_webhook_flips_paid_and_unlocks(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "paid flow", "vertical": "septic"})
        cid = r.json()["id"]
        # Upload 15 leads so trial (10) would block.
        rows = "name,phone\n" + "\n".join(f"L{i},(229) 555-0{str(i).zfill(3)}" for i in range(15))
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", rows.encode(), "text/csv")},
        )

        # Unpaid + over trial → 402.
        r = await c.post(f"/api/campaigns/{cid}/generate")
        assert r.status_code == 402, r.text
        assert "trial exhausted" in r.json()["detail"].lower()

        # Simulate payment.
        r = await c.post(
            "/webhooks/stripe",
            data={"_demo": "1", "campaign_id": str(cid), "session_id": "cs_demo_x"},
        )
        assert r.status_code == 200
        assert r.json()["paid"] is True

        # Now generation works.
        r = await c.post(f"/api/campaigns/{cid}/generate")
        assert r.status_code == 200
        assert r.json()["messages"] == 60  # 15 leads × 4 msgs


@pytest.mark.asyncio
async def test_trial_allows_first_10_leads(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "trial", "vertical": "septic"})
        cid = r.json()["id"]
        # 8 leads — comfortably inside trial.
        rows = "name,phone\n" + "\n".join(f"L{i},(229) 555-0{str(100+i).zfill(3)}" for i in range(8))
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", rows.encode(), "text/csv")},
        )
        r = await c.post(f"/api/campaigns/{cid}/generate")
        assert r.status_code == 200
        assert r.json()["trial_leads_used"] == 8


@pytest.mark.asyncio
async def test_signature_verification_math():
    from app.services.billing import verify_stripe_signature
    import hmac, hashlib, time
    secret = "whsec_test"
    payload = b'{"ok": true}'
    ts = str(int(time.time()))
    signed = f"{ts}.".encode() + payload
    v1 = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={v1}"
    assert verify_stripe_signature(payload, header, secret) is True
    assert verify_stripe_signature(payload, header, "wrong") is False
    assert verify_stripe_signature(payload, "garbage", secret) is False
