"""M4 tests: scheduler tick picks up due messages, respects quiet hours,
and transitions lead state."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

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


def test_quiet_hours_respects_area_code_tz():
    from app.services.quiet_hours import is_within_quiet_window

    # 06:00 ET — too early for an Atlanta lead (area 229 == ET).
    utc_6am_et = datetime(2026, 4, 22, 10, 0, tzinfo=ZoneInfo("UTC"))  # 10 UTC = 6am ET
    assert is_within_quiet_window("+12295550142", now_utc=utc_6am_et) is False

    # 09:00 ET — inside the window.
    utc_9am_et = datetime(2026, 4, 22, 13, 0, tzinfo=ZoneInfo("UTC"))  # 13 UTC = 9am ET
    assert is_within_quiet_window("+12295550142", now_utc=utc_9am_et) is True

    # 23:30 ET — too late.
    utc_late = datetime(2026, 4, 23, 3, 30, tzinfo=ZoneInfo("UTC"))  # prev day 23:30 ET
    assert is_within_quiet_window("+12295550142", now_utc=utc_late) is False


def test_area_code_defaults_to_et_for_unknown():
    from app.services.quiet_hours import tz_for_phone
    assert str(tz_for_phone("+19995551234")) == "America/New_York"
    assert str(tz_for_phone(None)) == "America/New_York"


@pytest.mark.asyncio
async def test_tick_sends_due_messages_and_advances_state(app, monkeypatch):
    # Force "not in quiet hours" so the tick will send regardless of wall-clock.
    monkeypatch.setattr("app.services.scheduler.is_within_quiet_window", lambda *_a, **_kw: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "sched", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nTest Guy,(229) 555-0190\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

    # Backdate all messages to "due now" and check they send.
    from app.db import SessionLocal
    from app.models.orm import Lead, Message
    from app.services.scheduler import tick

    db = SessionLocal()
    try:
        past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        db.query(Message).filter(Message.status == "pending").update({"scheduled_for": past})
        db.commit()

        result = tick(db=db)
        assert result["sent"] == 4  # all 4 messages for the one lead
        assert result["failed"] == 0

        # Re-ticking yields zero new sends.
        result2 = tick(db=db)
        assert result2["sent"] == 0

        # Lead advanced to contacted.
        lead = db.query(Lead).first()
        assert lead.state == "contacted"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_tick_skips_quiet_hours(app, monkeypatch):
    monkeypatch.setattr("app.services.scheduler.is_within_quiet_window", lambda *_a, **_kw: False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "quiet", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nNight Owl,(229) 555-0175\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

    from app.db import SessionLocal
    from app.models.orm import Message
    from app.services.scheduler import tick
    db = SessionLocal()
    try:
        past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        db.query(Message).filter(Message.status == "pending").update({"scheduled_for": past})
        db.commit()

        result = tick(db=db)
        assert result["sent"] == 0
        assert result["skipped_quiet"] == 4

        # Messages remain pending, not failed.
        pending = db.query(Message).filter(Message.status == "pending").count()
        assert pending == 4
    finally:
        db.close()


@pytest.mark.asyncio
async def test_tick_skips_opted_out_leads(app, monkeypatch):
    monkeypatch.setattr("app.services.scheduler.is_within_quiet_window", lambda *_a, **_kw: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "opt-out", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nOpt Out,(229) 555-0177\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        e164 = leads[0]["phone"]
        await c.post("/webhooks/twilio/inbound", data={"From": e164, "Body": "STOP"})

    from app.db import SessionLocal
    from app.models.orm import Message
    from app.services.scheduler import tick
    db = SessionLocal()
    try:
        past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        db.query(Message).filter(Message.status == "pending").update({"scheduled_for": past})
        db.commit()
        result = tick(db=db)
        # All messages were already cancelled by the STOP handler.
        assert result["sent"] == 0
    finally:
        db.close()
