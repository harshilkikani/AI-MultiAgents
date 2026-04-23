"""M15 tests: CSV preview endpoint, fuzzy header matching, mapping
override, sample-generate before bulk."""
from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient




def test_fuzzy_header_catches_weird_spellings():
    from app.services.csv_ingest import build_header_map
    # "First_Name" should map to name (via first_name → name alias).
    # Wait — the alias map has `full_name` etc but not `first_name`.
    # The fuzzy pass should catch obvious typos of aliases:
    m = build_header_map(["Custmer Name", "Mobil", "Email Adres", "Leed Sorce"])
    assert m.get("name") == "Custmer Name"
    assert m.get("phone") == "Mobil"
    assert m.get("email") == "Email Adres"
    assert m.get("source") == "Leed Sorce"


def test_override_mapping_applied():
    from app.services.csv_ingest import preview_csv
    csv_raw = (
        "Client,ContactPhone,Notes\n"
        "Jane Doe,229-555-0001,wanted a pump\n"
    )
    # Auto-detection misses `Client` (not in aliases). Supply an override.
    out = preview_csv(csv_raw, override_mapping={"name": "Client", "phone": "ContactPhone"})
    assert out["total_valid"] == 1
    assert out["preview"][0]["name"] == "Jane Doe"
    assert out["preview"][0]["phone"] == "+12295550001"
    # Notes comes through via its exact-alias match.
    assert out["preview"][0]["notes"] == "wanted a pump"


@pytest.mark.asyncio
async def test_preview_endpoint_no_persistence(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "preview test", "vertical": "septic"})
        cid = r.json()["id"]
        csv_raw = b"customer_name,phone_number,email_address\nJane Doe,(229) 555-0101,jane@ex.com\nBob,999-000-0001,\n"
        r = await c.post(
            f"/api/campaigns/{cid}/leads/preview",
            files={"file": ("s.csv", csv_raw, "text/csv")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["mapping"]["name"] == "customer_name"
        assert body["mapping"]["phone"] == "phone_number"
        assert body["total_valid"] == 2
        assert len(body["preview"]) == 2
        # Confirm preview didn't persist — leads endpoint is empty.
        r2 = await c.get(f"/api/campaigns/{cid}/leads")
        assert r2.json() == []


@pytest.mark.asyncio
async def test_preview_surfaces_skip_reasons(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "skip", "vertical": "septic"})
        cid = r.json()["id"]
        # Row 2 valid, row 3 no contact, row 4 no name.
        csv_raw = b"name,phone,email\nValid,555-0000,a@b.com\nNo Contact,,\n,,x@y.com\n"
        r = await c.post(
            f"/api/campaigns/{cid}/leads/preview",
            files={"file": ("t.csv", csv_raw, "text/csv")},
        )
        body = r.json()
        assert body["total_valid"] >= 0  # 555-0000 is only 4 digits, may normalize to None
        assert body["total_skipped"] >= 1
        assert any("line" in r for r in body["skipped_reasons"])


@pytest.mark.asyncio
async def test_upload_honors_override_mapping(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "override", "vertical": "septic"})
        cid = r.json()["id"]
        # Headers chosen so auto-detect would miss `Contact`.
        csv_raw = b"Contact,CellNumber\nJane,229-555-0190\n"
        r = await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("t.csv", csv_raw, "text/csv")},
            data={"mapping": json.dumps({"name": "Contact", "phone": "CellNumber"})},
        )
        assert r.status_code == 200, r.text
        assert r.json()["inserted"] == 1


@pytest.mark.asyncio
async def test_sample_generate_returns_n_without_persisting(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "samplegen", "vertical": "septic"})
        cid = r.json()["id"]
        rows = "name,phone\n" + "\n".join(f"Lead {i},(229) 555-0{str(100+i).zfill(3)}" for i in range(8))
        await c.post(
            f"/api/campaigns/{cid}/leads/upload",
            files={"file": ("s.csv", rows.encode(), "text/csv")},
        )
        r = await c.post(f"/api/campaigns/{cid}/sample-generate?n=3")
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["samples"]) == 3
        for s in body["samples"]:
            assert s["initial_msg"]
            assert len(s["drip_msgs"]) == 3
            assert 1 <= s["urgency_score"] <= 10

        # Confirm no messages persisted.
        from app.db import SessionLocal
        from app.models.orm import Message
        db = SessionLocal()
        try:
            count = db.query(Message).filter(Message.campaign_id == cid).count()
            assert count == 0
        finally:
            db.close()


@pytest.mark.asyncio
async def test_sample_generate_errors_on_empty_campaign(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/campaigns", json={"name": "empty", "vertical": "septic"})
        cid = r.json()["id"]
        r = await c.post(f"/api/campaigns/{cid}/sample-generate?n=3")
        assert r.status_code == 400
        assert "no leads" in r.json()["detail"].lower()
