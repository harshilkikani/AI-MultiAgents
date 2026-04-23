"""M9 tests: demo seed produces a campaign with the promised mix."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient




@pytest.mark.asyncio
async def test_demo_info_unseeded_then_seeded(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/demo/info")
        assert r.status_code == 200
        assert r.json()["seeded"] is False

        r = await c.post("/api/demo/reset")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["workspace_id"] == 2
        assert body["leads_loaded"] >= 190  # 200-row fixture, minus any with parse issues
        assert body["total"] == body["leads_loaded"]
        # Contacted is the count of leads that received at least Day-0.
        assert body["contacted"] == body["total"]
        # Mix: 40% of leads reply, but only the terminal-intent ones
        # (yes/no/stop → ~65% of replies) move OUT of `contacted`. Maybe
        # replies stay contacted so the drip continues. So terminal-reply
        # rate of total ≈ 40% × 65% ≈ 26%.
        replied = body["replied_hot"] + body["replied_no"] + body["opted_out"] + body["booked"]
        assert 0.15 * body["total"] <= replied <= 0.40 * body["total"], (
            f"terminal replies outside range: {replied} / {body['total']}"
        )
        assert body["booked"] >= 3

        r = await c.get("/api/demo/info")
        assert r.json()["seeded"] is True


@pytest.mark.asyncio
async def test_demo_workspace_isolated_from_default(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/api/demo/reset")
        # Default workspace should still see zero campaigns.
        r = await c.get("/api/campaigns", headers={"X-Workspace-Id": "1"})
        assert r.json() == []
        # Demo workspace should see its campaign.
        r = await c.get("/api/campaigns", headers={"X-Workspace-Id": "2"})
        assert len(r.json()) == 1
        assert r.json()[0]["name"] == "Spring 2026 Revival"


@pytest.mark.asyncio
async def test_demo_reset_is_idempotent(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r1 = await c.post("/api/demo/reset")
        r2 = await c.post("/api/demo/reset")
        # With the fixed RNG seed, repeated resets produce the same counts.
        for k in ("leads_loaded", "total", "booked", "replied_hot", "replied_no", "opted_out"):
            assert r1.json()[k] == r2.json()[k], f"{k} differs across resets"
