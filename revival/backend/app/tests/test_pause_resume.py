"""M17 tests: pause/resume campaign endpoints + scheduler honors pause."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient




@pytest.mark.asyncio
async def test_new_campaign_is_not_paused(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "new", "vertical": "septic"})
        assert r.status_code == 201
        assert r.json()["paused"] is False


@pytest.mark.asyncio
async def test_pause_and_resume_flip_flag(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "toggle", "vertical": "septic"})
        cid = r.json()["id"]

        r = await c.post(f"/api/campaigns/{cid}/pause")
        assert r.status_code == 200
        assert r.json()["paused"] is True
        assert r.json()["paused_at"] is not None

        # Re-pausing is idempotent.
        r = await c.post(f"/api/campaigns/{cid}/pause")
        assert r.status_code == 200
        assert r.json()["paused"] is True

        r = await c.post(f"/api/campaigns/{cid}/resume")
        assert r.status_code == 200
        assert r.json()["paused"] is False
        assert r.json()["paused_at"] is None


@pytest.mark.asyncio
async def test_paused_campaign_not_picked_up_by_scheduler(app, monkeypatch):
    from app.services import scheduler as sched_mod, compliance as comp_mod
    monkeypatch.setattr(sched_mod, "is_within_quiet_window", lambda *a, **kw: True)
    comp_mod.invalidate_dnc_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "paused", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nPause Me,(229) 555-0170\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

        # Pause before first tick.
        await c.post(f"/api/campaigns/{cid}/pause")

    from app.db import SessionLocal
    from app.models.orm import Message
    db = SessionLocal()
    try:
        past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        db.query(Message).filter(Message.status == "pending").update({"scheduled_for": past})
        db.commit()
        result = sched_mod.tick(db=db)
        assert result["sent"] == 0
        # Pending messages remain pending — nothing cancelled, just skipped.
        pending = db.query(Message).filter(Message.status == "pending").count()
        assert pending == 4
    finally:
        db.close()

    # Resume and tick again — all four send.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post(f"/api/campaigns/{cid}/resume")

    db = SessionLocal()
    try:
        result = sched_mod.tick(db=db)
        assert result["sent"] == 4
    finally:
        db.close()


@pytest.mark.asyncio
async def test_manual_send_blocked_while_paused(app):
    from app.services import compliance as comp_mod
    comp_mod.invalidate_dnc_cache()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "manual pause", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nManual Pause,(229) 555-0172\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")
        await c.post(f"/api/campaigns/{cid}/pause")

        from app.db import SessionLocal
        from app.models.orm import Message
        db = SessionLocal()
        try:
            msg_id = db.query(Message).filter(Message.campaign_id == cid, Message.step == 0).first().id
        finally:
            db.close()

        r = await c.post(f"/api/messages/{msg_id}/send")
        assert r.status_code == 409
        assert "paused" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pause_404_on_unknown_campaign(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns/9999/pause")
        assert r.status_code == 404
