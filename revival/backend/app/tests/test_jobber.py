"""M18 tests: Jobber OAuth stub + sync + dedup."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient




async def _new_campaign(c: AsyncClient) -> int:
    r = await c.post("/api/campaigns", json={"name": "jobber", "vertical": "septic"})
    return r.json()["id"]


@pytest.mark.asyncio
async def test_status_reports_disconnected_until_callback(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/integrations/jobber")
        assert r.status_code == 200
        assert r.json()["connected"] is False


@pytest.mark.asyncio
async def test_demo_connect_end_to_end(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/integrations/jobber/connect")
        body = r.json()
        assert body["mode"] == "demo"
        auth_url = body["authorize_url"]
        # The frontend would open this — in demo the URL points at our own
        # callback with a fake code.
        r2 = await c.get(auth_url)
        assert r2.status_code == 200
        out = r2.json()
        assert out["connected"] is True
        assert out["account_name"] == "Demo Jobber Shop"

        # Status should now reflect the connection.
        r3 = await c.get("/api/integrations/jobber")
        assert r3.json()["connected"] is True


@pytest.mark.asyncio
async def test_sync_inserts_leads_and_then_dedups(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid = await _new_campaign(c)
        # Connect
        conn = await c.post("/api/integrations/jobber/connect")
        await c.get(conn.json()["authorize_url"])

        # First sync — fresh leads.
        r = await c.post(f"/api/integrations/jobber/sync?campaign_id={cid}")
        assert r.status_code == 200, r.text
        first = r.json()
        assert first["pulled"] == 20
        assert first["inserted"] >= 10      # fake data may skip a few without phone/email
        assert first["already_present"] == 0

        # Second sync same day — deterministic RNG means same rows, all
        # already present, zero inserts.
        r = await c.post(f"/api/integrations/jobber/sync?campaign_id={cid}")
        second = r.json()
        assert second["pulled"] == 20
        assert second["inserted"] == 0
        assert second["already_present"] >= 10


@pytest.mark.asyncio
async def test_sync_without_connection_errors_400(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid = await _new_campaign(c)
        r = await c.post(f"/api/integrations/jobber/sync?campaign_id={cid}")
        assert r.status_code == 400
        assert "connect" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_disconnect_flips_status(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        conn = await c.post("/api/integrations/jobber/connect")
        await c.get(conn.json()["authorize_url"])

        r = await c.post("/api/integrations/jobber/disconnect")
        assert r.status_code == 200

        r = await c.get("/api/integrations/jobber")
        assert r.json()["connected"] is False


@pytest.mark.asyncio
async def test_leads_from_jobber_are_tagged_with_external_source(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid = await _new_campaign(c)
        conn = await c.post("/api/integrations/jobber/connect")
        await c.get(conn.json()["authorize_url"])
        await c.post(f"/api/integrations/jobber/sync?campaign_id={cid}")

    from app.db import SessionLocal
    from app.models.orm import Lead
    db = SessionLocal()
    try:
        leads = db.query(Lead).filter(Lead.campaign_id == cid).all()
        assert len(leads) >= 10
        assert all(l.external_source == "jobber" for l in leads)
        assert all(l.external_id and l.external_id.startswith("client_") for l in leads)
    finally:
        db.close()
