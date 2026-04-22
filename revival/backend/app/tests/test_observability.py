"""M20 tests: audit log captures state transitions, scheduler health
reports freshness, /api/health returns 503 on stale scheduler."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
async def test_campaign_create_writes_audit_event(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "audit c", "vertical": "septic"})
        cid = r.json()["id"]
        r = await c.get(f"/api/campaigns/{cid}/audit")
        assert r.status_code == 200
        events = r.json()
        assert any(e["event_type"] == "campaign.created" for e in events)


@pytest.mark.asyncio
async def test_pause_and_resume_write_audit(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "pause audit", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(f"/api/campaigns/{cid}/pause")
        await c.post(f"/api/campaigns/{cid}/resume")

        events = (await c.get(f"/api/campaigns/{cid}/audit")).json()
        types = [e["event_type"] for e in events]
        assert "campaign.paused" in types
        assert "campaign.resumed" in types


@pytest.mark.asyncio
async def test_inbound_reply_writes_audit_with_state_diff(app):
    from app.services import compliance as comp
    comp.invalidate_dnc_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "inbound audit", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nAudit Test,(229) 555-0191\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        phone = leads[0]["phone"]
        await c.post("/webhooks/twilio/inbound",
                     data={"From": phone, "Body": "yes please"})

        events = (await c.get(f"/api/campaigns/{cid}/audit")).json()
        inbound = [e for e in events if e["event_type"] == "lead.inbound_classified"]
        assert len(inbound) == 1
        ev = inbound[0]
        assert ev["before"]["state"] == "queued"
        assert ev["after"]["state"] == "replied_hot"
        assert ev["after"]["intent"] == "yes"


@pytest.mark.asyncio
async def test_scheduler_tick_writes_audit(app, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from app.services import scheduler as sched_mod, compliance as comp_mod
    monkeypatch.setattr(sched_mod, "is_within_quiet_window", lambda *a, **kw: True)
    comp_mod.invalidate_dnc_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "sched audit", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nSched Test,(229) 555-0193\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

    from app.db import SessionLocal
    from app.models.orm import Message
    db = SessionLocal()
    try:
        past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        db.query(Message).filter(Message.status == "pending").update({"scheduled_for": past})
        db.commit()
        result = sched_mod.tick(db=db)
        assert result["sent"] == 4
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        events = (await c.get(f"/api/campaigns/{cid}/audit")).json()
        sends = [e for e in events if e["event_type"] == "message.sent"]
        assert len(sends) == 4
        # Each send event should include state diff in meta.
        for s in sends:
            assert s["meta"]["state_before"] in ("queued", "contacted")
            assert s["meta"]["state_after"] in ("contacted",)


@pytest.mark.asyncio
async def test_health_reports_scheduler_status(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert "scheduler" in body
        # DISABLE_SCHEDULER=1 in tests — so enabled should be False.
        assert body["scheduler"]["enabled"] is False


@pytest.mark.asyncio
async def test_health_returns_503_on_stale_scheduler(tmp_path, monkeypatch):
    """If the scheduler is supposedly on (DISABLE_SCHEDULER unset) but
    hasn't ticked in >30 min, /api/health must return 503 so LB restarts."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.delenv("DISABLE_SCHEDULER", raising=False)

    import sys
    for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        sys.modules.pop(mod, None)

    from app.db import init_db
    from app.main import app as fresh_app
    init_db()
    # Manually set an ancient heartbeat.
    from app.services import scheduler as sched_mod
    sched_mod._last_tick_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)

    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://t") as c:
        r = await c.get("/api/health")
        assert r.status_code == 503
        assert r.json()["scheduler"]["stale"] is True


@pytest.mark.asyncio
async def test_jobber_sync_writes_audit(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "jobber audit", "vertical": "septic"})
        cid = r.json()["id"]
        conn = await c.post("/api/integrations/jobber/connect")
        await c.get(conn.json()["authorize_url"])
        await c.post(f"/api/integrations/jobber/sync?campaign_id={cid}")

        events = (await c.get(f"/api/campaigns/{cid}/audit")).json()
        jobber_events = [e for e in events if e["event_type"] == "jobber.sync"]
        assert len(jobber_events) == 1
        assert "inserted" in jobber_events[0]["meta"]
