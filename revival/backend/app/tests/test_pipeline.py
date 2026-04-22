"""M2 acceptance tests: 10 leads -> 40 messages, shape-valid, under the
token budget. Runs in DEMO_MODE so no network calls."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "sample_leads.csv"


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


@pytest.mark.asyncio
async def test_template_output_shape_matches_claude_contract():
    """The template path must produce the exact same shape the Claude path
    promises, so DEMO_MODE stays a faithful preview."""
    from app.services.revival_pipeline import RevivalOutput
    from app.services.revival_templates import LeadContext, generate_revival

    out = generate_revival(LeadContext(
        name="Dale Hatcher", vertical="septic", source="Facebook Lead Ad",
        last_contact=date(2025, 10, 1), notes="asked for pump quote",
        age_days=203, avg_ticket=680,
    ))
    # Pydantic validates shape + constraints.
    RevivalOutput.model_validate(out)
    # Each message must fit comfortably in a single SMS segment (~160 chars)
    # plus one concatenation. 320 cap is the STRICT safety rail.
    for m in [out["initial_msg"]] + out["drip_msgs"]:
        assert 20 <= len(m) <= 320, f"bad msg length {len(m)}: {m!r}"
    # First-name should appear in every message (personalization sanity).
    for m in [out["initial_msg"]] + out["drip_msgs"]:
        assert "Dale" in m, f"first name missing in {m!r}"


@pytest.mark.asyncio
async def test_generate_endpoint_creates_4_messages_per_lead(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "pipe test", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("s.csv", FIXTURE.read_bytes(), "text/csv")},
        )

        r = await c.post(f"/api/campaigns/{cid}/generate")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["leads"] >= 10, "fixture should have given us at least 10 leads"
        # Exactly 4 messages per lead.
        assert body["messages"] == body["leads"] * 4

        # Idempotent re-run: re-generating should yield the same message count.
        r2 = await c.post(f"/api/campaigns/{cid}/generate")
        assert r2.json()["messages"] == body["messages"]


@pytest.mark.asyncio
async def test_messages_scheduled_at_day_0_3_10_24(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "scheduling", "vertical": "hvac"})
        cid = r.json()["id"]
        # Upload tiny CSV with one lead so we can inspect timing.
        tiny = b"name,phone\nTest User,555-0001\n"
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", tiny, "text/csv")},
        )
        # The seed phone 555-0001 is too short to normalize; insert via a
        # valid one instead.
        tiny2 = b"name,phone\nTest User,229-555-0001\n"
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t2.csv", tiny2, "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")

    # Inspect directly via ORM to avoid needing a messages endpoint yet.
    from app.db import SessionLocal
    from app.models.orm import Message
    db = SessionLocal()
    try:
        msgs = db.query(Message).filter(Message.campaign_id == cid).order_by(Message.step).all()
        # We expect at least one lead with 4 messages.
        assert len(msgs) >= 4
        steps = [m.step for m in msgs[:4]]
        assert steps == [0, 1, 2, 3]
        deltas = [(m.scheduled_for - msgs[0].scheduled_for).days for m in msgs[:4]]
        assert deltas == [0, 3, 10, 24], f"bad drip offsets: {deltas}"
    finally:
        db.close()
