"""End-to-end smoke test: spin up the FastAPI app in-process via httpx's
ASGITransport, create a campaign, upload the fixture CSV, assert counts."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "sample_leads.csv"


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Use a scratch SQLite per test so state doesn't leak. Env must be set
    # BEFORE any app.* module imports — so purge sys.modules first, then let
    # the fresh imports pick up the current DATABASE_URL.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEMO_MODE", "true")

    import sys
    for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        sys.modules.pop(mod, None)

    from app.db import init_db
    from app.main import app as fresh_app
    # ASGITransport doesn't fire lifespan events; create tables directly.
    init_db()
    return fresh_app


@pytest.mark.asyncio
async def test_health_and_csv_upload(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/health")
        assert r.status_code == 200
        assert r.json()["demo_mode"] is True

        r = await c.post("/api/campaigns", json={"name": "April Revival", "vertical": "septic", "avg_ticket": 680})
        assert r.status_code == 201, r.text
        campaign_id = r.json()["id"]
        assert r.json()["lead_count"] == 0

        files = {"file": ("sample_leads.csv", FIXTURE.read_bytes(), "text/csv")}
        r = await c.post(f"/api/campaigns/{campaign_id}/leads/upload", files=files)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["inserted"] >= 190
        assert len(body["preview"]) == 5

        r = await c.get(f"/api/campaigns/{campaign_id}/leads?limit=10")
        assert r.status_code == 200
        assert len(r.json()) == 10

        r = await c.get(f"/api/campaigns/{campaign_id}")
        assert r.json()["lead_count"] == body["inserted"]
