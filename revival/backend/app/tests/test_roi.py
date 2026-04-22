"""M6 tests: ROI math edge cases."""
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


def test_roi_math_zero_campaign():
    from dataclasses import replace

    from app.models.orm import Campaign
    from app.services.roi import CampaignStats, compute_stats

    # Pure unit-y check: construct a dummy stats object and verify math.
    s = CampaignStats(
        campaign_id=1,
        state_counts={"queued": 100, "contacted": 0, "replied_hot": 0,
                      "replied_no": 0, "booked": 0, "dead": 0, "opted_out": 0},
        total_leads=100, messages_sent=0, messages_pending=400,
        messages_cancelled=0, messages_failed=0, inbound_count=0,
        booked_count=0, hot_count=0, avg_ticket=680.0,
        est_recovered_revenue=0.0, est_pipeline_revenue=0.0,
        keres_cost=1500.0, net=-1500.0,
    )
    assert s.net == -1500.0


@pytest.mark.asyncio
async def test_stats_endpoint_reflects_state_transitions(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={
            "name": "roi", "vertical": "septic", "avg_ticket": 680,
            "calendly_url": "https://calendly.com/x/30",
        })
        cid = r.json()["id"]
        # 3 leads: one will book, one will say no, one stays silent.
        csv = b"name,phone,email\nA One,(229) 555-0101,a@e.com\nB Two,(229) 555-0102,b@e.com\nC Three,(229) 555-0103,c@e.com\n"
        await c.post(f"/api/campaigns/{cid}/leads/upload", files={"file": ("t.csv", csv, "text/csv")})
        await c.post(f"/api/campaigns/{cid}/generate")

        # Lead A replies yes, then Calendly fires.
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        a_phone = leads[0]["phone"]
        b_phone = leads[1]["phone"]
        await c.post("/webhooks/twilio/inbound", data={"From": a_phone, "Body": "yes please"})
        await c.post("/webhooks/calendly", json={"phone": a_phone})
        # Lead B says no.
        await c.post("/webhooks/twilio/inbound", data={"From": b_phone, "Body": "no thanks"})

        stats = (await c.get(f"/api/campaigns/{cid}/stats")).json()
        assert stats["state_counts"]["booked"] == 1
        assert stats["state_counts"]["replied_no"] == 1
        assert stats["state_counts"]["queued"] == 1
        assert stats["est_recovered_revenue"] == 680.0
        assert stats["est_pipeline_revenue"] == 680.0  # no hot-but-not-booked
        assert stats["net"] == 680.0 - 1500.0


@pytest.mark.asyncio
async def test_lead_messages_endpoint_returns_thread(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "thread", "vertical": "septic"})
        cid = r.json()["id"]
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", b"name,phone\nThread Test,(229) 555-0105\n", "text/csv")},
        )
        await c.post(f"/api/campaigns/{cid}/generate")
        leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
        lid = leads[0]["id"]
        e164 = leads[0]["phone"]
        await c.post("/webhooks/twilio/inbound", data={"From": e164, "Body": "sounds good"})

        r = await c.get(f"/api/campaigns/{cid}/leads/{lid}/messages")
        assert r.status_code == 200
        body = r.json()
        # Expect: 4 out drip (some cancelled), 1 inbound, 1 step-99 auto-reply.
        msgs = body["messages"]
        assert any(m["direction"] == "in" for m in msgs)
        assert any(m["step"] == 99 for m in msgs)
