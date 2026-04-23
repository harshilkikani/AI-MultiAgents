"""M16 tests: owner alerts fire on replied_hot + booked, dedup within
4h, honor quiet hours, and skip when unconfigured."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient




async def _configure_owner(c: AsyncClient, phone="+14045551234", tz="America/New_York",
                            slack=None):
    body = {"owner_phone": phone, "owner_timezone": tz}
    if slack:
        body["slack_webhook_url"] = slack
    r = await c.patch("/api/workspace", json=body)
    assert r.status_code == 200, r.text


async def _seed_lead(c: AsyncClient) -> tuple[int, str]:
    r = await c.post("/api/campaigns", json={"name": "alerts", "vertical": "septic",
                                             "calendly_url": "https://calendly.com/x/30"})
    cid = r.json()["id"]
    await c.post(
        f"/api/campaigns/{cid}/leads/upload",
        files={"file": ("t.csv", b"name,phone\nHot Lead,(229) 555-0101\n", "text/csv")},
    )
    await c.post(f"/api/campaigns/{cid}/generate")
    leads = (await c.get(f"/api/campaigns/{cid}/leads")).json()
    return cid, leads[0]["phone"]


@pytest.mark.asyncio
async def test_workspace_settings_require_e164_and_valid_tz(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.patch("/api/workspace", json={"owner_phone": "4045551234"})
        assert r.status_code == 422
        r = await c.patch("/api/workspace", json={"owner_timezone": "America/Pheonix"})
        assert r.status_code == 422
        r = await c.patch("/api/workspace", json={"slack_webhook_url": "https://evil.example.com/hook"})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_replied_hot_fires_alert(app, monkeypatch):
    # Force owner tz into business hours so the SMS fires.
    from app.services import alerts as alerts_mod
    monkeypatch.setattr(alerts_mod, "is_within_owner_window", lambda *a, **kw: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await _configure_owner(c)
        cid, lead_phone = await _seed_lead(c)
        r = await c.post("/webhooks/twilio/inbound",
                         data={"From": lead_phone, "Body": "yes please"})
        assert r.status_code == 200

    from app.db import SessionLocal
    from app.models.orm import OwnerAlert
    db = SessionLocal()
    try:
        alerts = db.query(OwnerAlert).all()
        assert len(alerts) == 1
        assert alerts[0].alert_type == "replied_hot"
        assert alerts[0].channel == "sms"
        assert alerts[0].status == "sent"
        assert "wants to book" in alerts[0].body
    finally:
        db.close()


@pytest.mark.asyncio
async def test_alert_dedups_within_4h(app, monkeypatch):
    from app.services import alerts as alerts_mod
    monkeypatch.setattr(alerts_mod, "is_within_owner_window", lambda *a, **kw: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await _configure_owner(c)
        cid, lead_phone = await _seed_lead(c)
        await c.post("/webhooks/twilio/inbound",
                     data={"From": lead_phone, "Body": "yes"})
        # Second "yes" within the dedup window — no new alert.
        await c.post("/webhooks/twilio/inbound",
                     data={"From": lead_phone, "Body": "still yes"})

    from app.db import SessionLocal
    from app.models.orm import OwnerAlert
    db = SessionLocal()
    try:
        hot_alerts = db.query(OwnerAlert).filter(
            OwnerAlert.alert_type == "replied_hot", OwnerAlert.status == "sent"
        ).count()
        assert hot_alerts == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_quiet_hours_skips_sms_but_records_row(app, monkeypatch):
    from app.services import alerts as alerts_mod
    monkeypatch.setattr(alerts_mod, "is_within_owner_window", lambda *a, **kw: False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await _configure_owner(c)
        cid, lead_phone = await _seed_lead(c)
        await c.post("/webhooks/twilio/inbound", data={"From": lead_phone, "Body": "yes"})

    from app.db import SessionLocal
    from app.models.orm import OwnerAlert
    db = SessionLocal()
    try:
        alerts = db.query(OwnerAlert).all()
        assert len(alerts) == 1
        assert alerts[0].status == "skipped"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_no_owner_phone_no_alert(app, monkeypatch):
    from app.services import alerts as alerts_mod
    monkeypatch.setattr(alerts_mod, "is_within_owner_window", lambda *a, **kw: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        cid, lead_phone = await _seed_lead(c)
        await c.post("/webhooks/twilio/inbound", data={"From": lead_phone, "Body": "yes"})

    from app.db import SessionLocal
    from app.models.orm import OwnerAlert
    db = SessionLocal()
    try:
        assert db.query(OwnerAlert).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_booked_fires_second_alert(app, monkeypatch):
    from app.services import alerts as alerts_mod
    monkeypatch.setattr(alerts_mod, "is_within_owner_window", lambda *a, **kw: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await _configure_owner(c)
        cid, lead_phone = await _seed_lead(c)
        await c.post("/webhooks/twilio/inbound", data={"From": lead_phone, "Body": "yes"})
        # Calendly fires — state → booked, second alert fires.
        await c.post("/webhooks/calendly", json={"phone": lead_phone})

    from app.db import SessionLocal
    from app.models.orm import OwnerAlert
    db = SessionLocal()
    try:
        alerts = db.query(OwnerAlert).order_by(OwnerAlert.id).all()
        types = [a.alert_type for a in alerts]
        assert "replied_hot" in types
        assert "booked" in types
        booked = next(a for a in alerts if a.alert_type == "booked")
        assert "booked a slot" in booked.body
    finally:
        db.close()


@pytest.mark.asyncio
async def test_slack_channel_fires_even_in_quiet_hours(app, monkeypatch):
    # Outside owner quiet hours → SMS skipped, Slack still attempted.
    from app.services import alerts as alerts_mod
    monkeypatch.setattr(alerts_mod, "is_within_owner_window", lambda *a, **kw: False)
    # Fake Slack post success so the test doesn't hit the real network.
    monkeypatch.setattr(alerts_mod, "_slack_post", lambda url, text: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await _configure_owner(c, slack="https://hooks.slack.com/services/X/Y/Z")
        cid, lead_phone = await _seed_lead(c)
        await c.post("/webhooks/twilio/inbound", data={"From": lead_phone, "Body": "yes"})

    from app.db import SessionLocal
    from app.models.orm import OwnerAlert
    db = SessionLocal()
    try:
        alerts = db.query(OwnerAlert).all()
        channels = {a.channel for a in alerts}
        assert "sms" in channels       # recorded as skipped
        assert "slack" in channels     # fired successfully
        slack = next(a for a in alerts if a.channel == "slack")
        assert slack.status == "sent"
    finally:
        db.close()
