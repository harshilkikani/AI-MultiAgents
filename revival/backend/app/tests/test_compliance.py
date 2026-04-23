"""M11 tests: TCPA compliance — opt-outs, DNC, frequency cap, STOP footer,
audit events."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient




def test_should_include_stop_footer_only_on_step_2():
    from app.services.compliance import should_include_stop_footer
    assert should_include_stop_footer(0) is False   # Day-0 already has STOP text in the system prompt
    assert should_include_stop_footer(1) is False   # Day-3 keeps it lean
    assert should_include_stop_footer(2) is True    # Day-10 gets the reminder
    assert should_include_stop_footer(3) is False   # Day-24 is the closer


def test_dnc_check_loads_from_file():
    from app.services.compliance import invalidate_dnc_cache, is_on_dnc
    invalidate_dnc_cache()
    assert is_on_dnc("+19990000001") is True
    assert is_on_dnc("+19990000099") is False
    # Blank/None handled.
    assert is_on_dnc(None) is False  # type: ignore[arg-type]
    assert is_on_dnc("") is False


@pytest.mark.asyncio
async def test_stop_reply_writes_to_opt_outs_table(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "tcpa", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nTCPA Tester,(229) 555-0112\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        phone = leads[0]["phone"]

        await c.post("/webhooks/twilio/inbound", data={"From": phone, "Body": "STOP"})

        r = await c.get("/api/compliance/opt-outs")
        opt_outs = r.json()
        assert any(o["phone"] == phone for o in opt_outs)
        match = [o for o in opt_outs if o["phone"] == phone][0]
        assert match["source"] == "sms_reply"
        assert match["proof_body"] == "STOP"


@pytest.mark.asyncio
async def test_opt_out_blocks_future_campaigns_same_workspace(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Opt out a phone number directly.
        await c.post("/api/compliance/opt-outs",
                     json={"phone": "+12295550220", "reason": "called in"})

        # Create a fresh campaign in the same workspace with that phone.
        r = await c.post("/api/campaigns", json={"name": "post-optout", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nBlocked Guy,(229) 555-0220\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

    # Tick the scheduler with all messages due now and force not-quiet.
    from datetime import UTC, datetime, timedelta
    from app.db import SessionLocal
    from app.models.orm import Message
    from app.services import scheduler as sched_mod
    sched_mod.is_within_quiet_window = lambda *a, **kw: True  # monkeypatch

    db = SessionLocal()
    try:
        past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        db.query(Message).filter(Message.status == "pending").update({"scheduled_for": past})
        db.commit()
        result = sched_mod.tick(db=db)
        assert result["sent"] == 0
        assert result["blocked_compliance"] == 4
    finally:
        db.close()


@pytest.mark.asyncio
async def test_dnc_blocks_send_and_records_event(app, monkeypatch):
    from app.services import compliance as comp
    comp.invalidate_dnc_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "dnc", "vertical": "septic"})
        cid = r.json()["id"]
        # Use the DNC test number from data/dnc_deny.txt (+19990000001).
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nDNC Lead,999-000-0001\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

        r = await c.get("/api/compliance/events?event_type=dnc_blocked")
        # dnc_blocked only fires on attempted send, not on generate. Trigger a send.
        from app.db import SessionLocal
        from app.models.orm import Message
        from app.services import scheduler as sched_mod
        monkeypatch.setattr(sched_mod, "is_within_quiet_window", lambda *a, **kw: True)

        db = SessionLocal()
        try:
            from datetime import UTC, datetime, timedelta
            past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
            db.query(Message).filter(Message.status == "pending").update({"scheduled_for": past})
            db.commit()
            result = sched_mod.tick(db=db)
            assert result["sent"] == 0
            assert result["blocked_compliance"] == 4
        finally:
            db.close()

        r = await c.get("/api/compliance/events?event_type=dnc_blocked")
        events = r.json()
        assert len(events) == 4
        assert all(e["phone"] for e in events)


@pytest.mark.asyncio
async def test_frequency_cap_blocks_after_5_sends(app, monkeypatch):
    from app.db import SessionLocal
    from app.models.orm import Lead, Message
    from app.services import scheduler as sched_mod, compliance as comp

    comp.invalidate_dnc_cache()
    monkeypatch.setattr(sched_mod, "is_within_quiet_window", lambda *a, **kw: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "freq", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nFreq Victim,(229) 555-0311\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

    # Hand-insert 5 prior sent messages to this phone so we're at the cap.
    db = SessionLocal()
    try:
        lead = db.query(Lead).first()
        now = datetime.now(UTC).replace(tzinfo=None)
        for i in range(5):
            db.add(Message(
                workspace_id=lead.workspace_id, lead_id=lead.id, campaign_id=lead.campaign_id,
                step=100 + i, body=f"prior msg {i}", direction="out",
                status="sent", sent_at=now - timedelta(days=i + 1),
                twilio_sid=f"SM_prior_{i}",
            ))
        db.commit()

        # Backdate this campaign's pending messages.
        past = now - timedelta(minutes=5)
        db.query(Message).filter(Message.status == "pending").update({"scheduled_for": past})
        db.commit()

        result = sched_mod.tick(db=db)
        assert result["sent"] == 0
        assert result["blocked_compliance"] == 4
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/compliance/events?event_type=frequency_capped")
        assert r.status_code == 200
        assert len(r.json()) == 4


@pytest.mark.asyncio
async def test_manual_opt_out_cancels_pending(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "manual", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nManual OO,(229) 555-0420\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        e164 = leads[0]["phone"]

        r = await c.post("/api/compliance/opt-outs",
                         json={"phone": e164, "reason": "owner manually opted them out"})
        assert r.status_code == 201

        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        assert leads[0]["state"] == "opted_out"

    from app.db import SessionLocal
    from app.models.orm import Message
    db = SessionLocal()
    try:
        pending = db.query(Message).filter(
            Message.lead_id == leads[0]["id"], Message.status == "pending"
        ).count()
        assert pending == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_day_10_message_has_stop_reminder(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "footer", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nFooter Test,(229) 555-0222\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

    from app.db import SessionLocal
    from app.models.orm import Message
    db = SessionLocal()
    try:
        msgs = db.query(Message).filter(Message.campaign_id == cid).order_by(Message.step).all()
        assert "STOP" in msgs[0].body.upper()  # Day-0 from the template
        assert "STOP" in msgs[2].body.upper()  # Day-10 footer (step 2)
        # Day-3 and Day-24 do NOT have STOP — save chars for the ask.
        assert "STOP" not in msgs[1].body.upper()
        assert "STOP" not in msgs[3].body.upper()
    finally:
        db.close()
