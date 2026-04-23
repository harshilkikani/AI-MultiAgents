"""M5 tests: auto-reply on yes + Calendly webhook → booked."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient




async def _seed(c: AsyncClient, calendly: str | None = "https://calendly.com/hatcher-septic/30min") -> tuple[int, str]:
    r = await c.post("/api/campaigns", json={
        "name": "book test", "vertical": "septic", "calendly_url": calendly,
    })
    cid = r.json()["id"]
    await c.post(
        f"/api/campaigns/{cid}/leads/upload",
        files={"file": ("t.csv", b"name,phone,email\nJane Doe,(229) 555-0101,jane@ex.com\n", "text/csv")},
    )
    await c.post(f"/api/campaigns/{cid}/generate")
    leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
    return cid, leads[0]["phone"]


@pytest.mark.asyncio
async def test_yes_reply_sends_calendly_autoreply(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid, e164 = await _seed(c)
        r = await c.post("/webhooks/twilio/inbound", data={"From": e164, "Body": "yes please"})
        assert r.status_code == 200

        # Lead is replied_hot, drip messages cancelled, auto-reply stored.
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        assert leads[0]["state"] == "replied_hot"

    from app.db import SessionLocal
    from app.models.orm import Message
    db = SessionLocal()
    try:
        msgs = db.query(Message).filter(Message.campaign_id == cid).order_by(Message.id).all()
        # There should be an inbound, and a step=99 outbound auto-reply.
        outs = [m for m in msgs if m.step == 99]
        assert len(outs) == 1
        assert "calendly.com/hatcher-septic" in outs[0].body
        assert outs[0].status == "sent"
        # Remaining drip messages (steps 1/2/3) cancelled; step 0 may have
        # already been sent or still pending depending on scheduling.
        cancelled = [m for m in msgs if m.status == "cancelled"]
        assert len(cancelled) >= 3
    finally:
        db.close()


@pytest.mark.asyncio
async def test_yes_without_calendly_fallback_copy(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid, e164 = await _seed(c, calendly=None)
        await c.post("/webhooks/twilio/inbound", data={"From": e164, "Body": "sounds good"})
    from app.db import SessionLocal
    from app.models.orm import Message
    db = SessionLocal()
    try:
        out = db.query(Message).filter(Message.campaign_id == cid, Message.step == 99).first()
        assert out is not None
        assert "ring you back" in out.body
    finally:
        db.close()


@pytest.mark.asyncio
async def test_calendly_webhook_flips_to_booked(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid, e164 = await _seed(c)
        await c.post("/webhooks/twilio/inbound", data={"From": e164, "Body": "yes"})

        # Simulate Calendly invitee.created with phone match.
        r = await c.post("/webhooks/calendly", json={
            "event": "invitee.created",
            "payload": {"invitee": {"text_reminder_number": e164, "email": "jane@ex.com"}},
        })
        assert r.status_code == 200
        assert r.json()["matched"] is True

        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        assert leads[0]["state"] == "booked"


@pytest.mark.asyncio
async def test_calendly_webhook_by_email(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid, e164 = await _seed(c)
        await c.post("/webhooks/twilio/inbound", data={"From": e164, "Body": "yes"})
        r = await c.post("/webhooks/calendly", json={"email": "jane@ex.com"})
        assert r.status_code == 200
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        assert leads[0]["state"] == "booked"


@pytest.mark.asyncio
async def test_calendly_webhook_unknown_lead_is_ok(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/webhooks/calendly", json={"phone": "+19995550000"})
        assert r.status_code == 200
        assert r.json()["matched"] is False
