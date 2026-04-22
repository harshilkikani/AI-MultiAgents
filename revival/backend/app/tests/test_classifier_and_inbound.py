"""M3 tests: reply classifier heuristics + Twilio inbound webhook state
transitions + manual send endpoint."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEMO_MODE", "true")

    import sys
    for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        sys.modules.pop(mod, None)

    from app.db import init_db
    from app.main import app as fresh_app
    init_db()
    return fresh_app


def test_classifier_stop_wins_over_everything():
    from app.services.reply_classifier import classify_reply
    assert classify_reply("STOP") == "stop"
    assert classify_reply("Yes, please stop") == "stop"  # stop keyword wins
    assert classify_reply("unsubscribe me") == "stop"
    assert classify_reply("Please cancel") == "stop"


def test_classifier_yes_variants():
    from app.services.reply_classifier import classify_reply
    for s in ("yes", "YES please", "Yeah sounds good", "ok book it",
              "let's do it", "sure, come tomorrow", "sounds good, send the quote"):
        assert classify_reply(s) == "yes", s


def test_classifier_no_variants():
    from app.services.reply_classifier import classify_reply
    for s in ("no thanks", "not interested", "wrong number", "already hired someone",
              "went with another contractor", "pass"):
        assert classify_reply(s) == "no", s


def test_classifier_maybe_variants():
    from app.services.reply_classifier import classify_reply
    for s in ("how much does it cost?", "price?", "maybe next month",
              "call me later", "thinking about it", "what's the price"):
        assert classify_reply(s) == "maybe", s


def test_classifier_other_for_unknown():
    from app.services.reply_classifier import classify_reply
    for s in ("lol", "🙂", "hmm"):
        assert classify_reply(s) == "other", s


async def _seed_campaign_with_lead(c: AsyncClient, phone: str = "(229) 555-0199") -> tuple[int, int, str]:
    r = await c.post("/api/campaigns", json={"name": "wh test", "vertical": "septic"})
    cid = r.json()["id"]
    await c.post(
        f"/api/campaigns/{cid}/leads/upload",
        files={"file": ("t.csv", f"name,phone\nJane Doe,{phone}\n".encode(), "text/csv")},
    )
    leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
    # The phone comes back in E.164.
    return cid, leads[0]["id"], leads[0]["phone"]


@pytest.mark.asyncio
async def test_inbound_yes_transitions_to_replied_hot(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid, lead_id, e164 = await _seed_campaign_with_lead(c)
        await c.post(f"/api/campaigns/{cid}/generate")
        r = await c.post(
            "/webhooks/twilio/inbound",
            data={"From": e164, "Body": "yes please", "MessageSid": "SM_fake"},
        )
        assert r.status_code == 200
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        assert leads[0]["state"] == "replied_hot"


@pytest.mark.asyncio
async def test_inbound_stop_opts_out_and_cancels_pending(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid, lead_id, e164 = await _seed_campaign_with_lead(c)
        await c.post(f"/api/campaigns/{cid}/generate")
        r = await c.post("/webhooks/twilio/inbound", data={"From": e164, "Body": "STOP"})
        assert r.status_code == 200
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        assert leads[0]["state"] == "opted_out"

    # Check that pending messages got cancelled.
    from app.db import SessionLocal
    from app.models.orm import Message
    db = SessionLocal()
    try:
        pending = db.query(Message).filter(Message.lead_id == lead_id, Message.status == "pending").count()
        cancelled = db.query(Message).filter(Message.lead_id == lead_id, Message.status == "cancelled").count()
        assert pending == 0
        assert cancelled >= 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_inbound_unknown_phone_is_dropped_cleanly(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/webhooks/twilio/inbound", data={"From": "+19995550000", "Body": "hi"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_manual_send_in_demo_marks_sent(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid, lead_id, e164 = await _seed_campaign_with_lead(c)
        await c.post(f"/api/campaigns/{cid}/generate")
        # Pick the first message for this lead.
        from app.db import SessionLocal
        from app.models.orm import Message
        db = SessionLocal()
        try:
            msg = db.query(Message).filter(Message.lead_id == lead_id, Message.step == 0).first()
            msg_id = msg.id
        finally:
            db.close()

        r = await c.post(f"/api/messages/{msg_id}/send")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "demo"

        # Lead should now be in 'contacted' state.
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        assert leads[0]["state"] == "contacted"
