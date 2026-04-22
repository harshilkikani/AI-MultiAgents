"""M7 tests: cross-workspace reads are fully isolated. Workspaces plumb
through middleware today (header-selected); auth lives on top in M8."""
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
    # Seed a second workspace so tests can cross it.
    from app.db import SessionLocal
    from app.models.orm import Workspace
    db = SessionLocal()
    try:
        if db.get(Workspace, 2) is None:
            db.add(Workspace(id=2, name="Other workspace"))
            db.commit()
    finally:
        db.close()
    return fresh_app


@pytest.mark.asyncio
async def test_workspace_a_cannot_see_workspace_b_campaigns(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Create one campaign in ws 1, one in ws 2.
        r1 = await c.post("/api/campaigns", json={"name": "A", "vertical": "septic"},
                          headers={"X-Workspace-Id": "1"})
        r2 = await c.post("/api/campaigns", json={"name": "B", "vertical": "hvac"},
                          headers={"X-Workspace-Id": "2"})
        assert r1.status_code == 201
        assert r2.status_code == 201

        # ws 1 sees only its own.
        r = await c.get("/api/campaigns", headers={"X-Workspace-Id": "1"})
        ids1 = {x["id"] for x in r.json()}
        assert r1.json()["id"] in ids1
        assert r2.json()["id"] not in ids1

        # ws 2 sees only its own.
        r = await c.get("/api/campaigns", headers={"X-Workspace-Id": "2"})
        ids2 = {x["id"] for x in r.json()}
        assert r2.json()["id"] in ids2
        assert r1.json()["id"] not in ids2


@pytest.mark.asyncio
async def test_workspace_a_gets_404_on_workspace_b_campaign(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r2 = await c.post("/api/campaigns", json={"name": "B", "vertical": "hvac"},
                          headers={"X-Workspace-Id": "2"})
        cid_b = r2.json()["id"]
        r = await c.get(f"/api/campaigns/{cid_b}", headers={"X-Workspace-Id": "1"})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_leads_are_scoped(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r2 = await c.post("/api/campaigns", json={"name": "B", "vertical": "hvac"},
                          headers={"X-Workspace-Id": "2"})
        cid = r2.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nB Lead,(229) 555-0140\n", "text/csv")},
            headers={"X-Workspace-Id": "2"},
        )
        # ws 1 trying to list the leads of a ws 2 campaign → 404.
        r = await c.get(f"/api/campaigns/{cid}/leads", headers={"X-Workspace-Id": "1"})
        assert r.status_code == 404

        # ws 2 can see them.
        r = await c.get(f"/api/campaigns/{cid}/leads", headers={"X-Workspace-Id": "2"})
        assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_workspace_query_param_fallback(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns?workspace=2", json={"name": "via_qp", "vertical": "septic"})
        assert r.status_code == 201
        # Now confirm it lives in ws 2.
        r = await c.get("/api/campaigns", headers={"X-Workspace-Id": "2"})
        assert any(x["name"] == "via_qp" for x in r.json())


@pytest.mark.asyncio
async def test_invalid_workspace_header_falls_back_to_1(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Garbage header value → default to 1, not crash.
        r = await c.get("/api/campaigns", headers={"X-Workspace-Id": "not-an-int"})
        assert r.status_code == 200
