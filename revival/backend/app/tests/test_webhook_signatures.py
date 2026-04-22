"""M12 tests: signature verification actually enforces. These tests
disable the REVIVAL_TEST_BYPASS env var so they hit the real verifier."""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    # Turn off the test bypass so signature checks run for real.
    monkeypatch.delenv("REVIVAL_TEST_BYPASS", raising=False)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_twilio_token")
    monkeypatch.setenv("CALENDLY_WEBHOOK_SECRET", "test_calendly_secret")

    import sys
    for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        sys.modules.pop(mod, None)

    from app.db import init_db
    from app.main import app as fresh_app
    init_db()
    return fresh_app


@pytest.mark.asyncio
async def test_twilio_rejects_unsigned_request(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/webhooks/twilio/inbound",
                         data={"From": "+12295550199", "Body": "hello"})
        assert r.status_code == 403
        assert "twilio" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_twilio_rejects_invalid_signature(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/webhooks/twilio/inbound",
            data={"From": "+12295550199", "Body": "hello"},
            headers={"X-Twilio-Signature": "obviously-wrong"},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_twilio_accepts_valid_signature(app):
    """Feed a signature computed with the same algorithm Twilio uses."""
    from twilio.request_validator import RequestValidator
    validator = RequestValidator("test_twilio_token")
    # Must use the same URL + params the server will reconstruct.
    url = "http://t/webhooks/twilio/inbound"
    params = {"From": "+12295550199", "Body": "hello"}
    sig = validator.compute_signature(url, params)

    # Seed a campaign + lead so the inbound has somewhere to land.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        os.environ["REVIVAL_TEST_BYPASS"] = "1"
        r = await c.post("/api/campaigns", json={"name": "sigtest", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nSig Tester,(229) 555-0199\n", "text/csv")},
        )
        os.environ.pop("REVIVAL_TEST_BYPASS", None)

        r = await c.post(
            "/webhooks/twilio/inbound",
            data=params,
            headers={"X-Twilio-Signature": sig},
        )
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_calendly_rejects_unsigned(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/webhooks/calendly", json={"phone": "+1234567890"})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_calendly_accepts_valid_signature(app):
    body = b'{"email":"jane@ex.com"}'
    ts = str(int(time.time()))
    sig = hmac.new(b"test_calendly_secret", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/webhooks/calendly",
            content=body,
            headers={"Calendly-Webhook-Signature": header, "content-type": "application/json"},
        )
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_calendly_rejects_stale_timestamp(app):
    body = b'{"email":"jane@ex.com"}'
    stale_ts = str(int(time.time()) - 1000)  # > 5 min replay window
    sig = hmac.new(b"test_calendly_secret", f"{stale_ts}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={stale_ts},v1={sig}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/webhooks/calendly",
            content=body,
            headers={"Calendly-Webhook-Signature": header, "content-type": "application/json"},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_bypass_header_accepted_in_demo_mode(app):
    """X-Test-Signature-Bypass: 1 should work when DEMO_MODE=true — tests
    sign their own signatures via this escape hatch when needed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # No signature, but with the bypass header, we accept.
        r = await c.post(
            "/webhooks/calendly",
            json={"phone": "+1234567890"},
            headers={"X-Test-Signature-Bypass": "1"},
        )
        assert r.status_code == 200  # matched=False but 200 OK


def test_calendly_verifier_math():
    from app.services.webhook_auth import verify_calendly_request_sync
    secret = "s3cret"
    body = b'{"x": 1}'
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"
    assert verify_calendly_request_sync(body, header, secret) is True
    # Wrong secret.
    assert verify_calendly_request_sync(body, header, "other") is False
    # Tampered body.
    assert verify_calendly_request_sync(b"tampered", header, secret) is False
    # Missing header.
    assert verify_calendly_request_sync(body, None, secret) is False
