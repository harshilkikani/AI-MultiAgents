"""M19 tests: per-vertical prompt loading, tone_notes override, PATCH."""
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
    return fresh_app


def test_prompt_loader_picks_vertical_specific_file():
    from app.services.revival_pipeline import _load_prompt
    for v in ("septic", "roofing", "hvac", "plumbing", "electrical"):
        text = _load_prompt(v)
        assert v.upper() in text.upper() or v in text.lower(), \
            f"vertical {v!r} prompt should mention the vertical"


def test_prompt_loader_falls_back_to_generic_for_unknown_vertical():
    from app.services.revival_pipeline import _load_prompt
    # Deliberately bad vertical — should fall through to revival_system.txt
    # instead of raising.
    text = _load_prompt("automotive")
    assert "OUTPUT FORMAT" in text  # generic still has the shared output contract


@pytest.mark.asyncio
async def test_campaign_create_accepts_tone_notes(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={
            "name": "tone", "vertical": "septic",
            "tone_notes": "Keep it short. No y'all. We're a Boston shop.",
        })
        assert r.status_code == 201
        assert "Boston" in r.json()["tone_notes"]


@pytest.mark.asyncio
async def test_campaign_patch_updates_fields(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "patch", "vertical": "hvac"})
        cid = r.json()["id"]

        r = await c.patch(f"/api/campaigns/{cid}", json={
            "tone_notes": "Reference Florida heat, not generic summer.",
            "avg_ticket": 1400,
        })
        assert r.status_code == 200
        body = r.json()
        assert "Florida" in body["tone_notes"]
        assert body["avg_ticket"] == 1400

        # Blank tone_notes clears it.
        r = await c.patch(f"/api/campaigns/{cid}", json={"tone_notes": ""})
        assert r.json()["tone_notes"] is None


@pytest.mark.asyncio
async def test_patch_unknown_campaign_404(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.patch("/api/campaigns/9999", json={"tone_notes": "x"})
        assert r.status_code == 404
