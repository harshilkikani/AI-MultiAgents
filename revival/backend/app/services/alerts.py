# Why this exists: fire the shop owner a message the moment a lead goes
# hot or books. This is the single most valuable product moment — the
# owner gets a buzz on their phone while they're on a roof or driving a
# truck and can follow up within minutes. Dedup + quiet hours + Slack
# fallback all live here.
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Lead, OwnerAlert, Workspace
from app.services.quiet_hours import is_within_owner_window
from app.services.twilio_client import send_sms
from app.utils.logger import get_logger

log = get_logger("alerts")

ALERT_DEDUP_WINDOW = timedelta(hours=4)

AlertType = Literal["replied_hot", "booked"]


@dataclass
class AlertResult:
    fired: bool
    channel: Optional[str]
    reason: str  # "sent" | "dedup" | "quiet_hours" | "not_configured" | "failed"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _recent_alert(db: Session, workspace_id: int, lead_id: int, alert_type: AlertType) -> Optional[OwnerAlert]:
    cutoff = _now() - ALERT_DEDUP_WINDOW
    return db.scalars(
        select(OwnerAlert)
        .where(
            OwnerAlert.workspace_id == workspace_id,
            OwnerAlert.lead_id == lead_id,
            OwnerAlert.alert_type == alert_type,
            OwnerAlert.sent_at >= cutoff,
            OwnerAlert.status == "sent",
        )
        .order_by(OwnerAlert.sent_at.desc())
    ).first()


def _slack_post(webhook_url: str, text: str) -> bool:
    """Fire-and-forget POST to a Slack incoming webhook. Returns True on
    2xx, False otherwise. Network errors are logged and swallowed — owner
    alerts must never block the inbound webhook."""
    try:
        import httpx
        r = httpx.post(webhook_url, json={"text": text}, timeout=5.0)
        return 200 <= r.status_code < 300
    except Exception as e:
        log.warning("slack post failed: %s", e)
        return False


def _build_body(alert_type: AlertType, lead: Lead) -> str:
    first = (lead.name or "A lead").split()[0]
    phone = lead.phone or "(no phone)"
    if alert_type == "replied_hot":
        return f"🔥 {first} ({phone}) wants to book — open Lead Revival to reply."
    # booked
    return f"✅ {first} ({phone}) booked a slot — confirmed on your calendar."


def fire_alert(
    db: Session,
    *,
    workspace_id: int,
    lead_id: int,
    alert_type: AlertType,
) -> AlertResult:
    """Fire the owner alert. Idempotent within the dedup window. SMS is
    preferred channel; Slack is a parallel extra (not an alternative).

    DEMO_MODE: twilio_client.send_sms is already a no-op logger, and Slack
    webhooks will attempt a real HTTP POST if a URL is configured — that
    will just fail gracefully if the URL is fake.
    """
    lead = db.get(Lead, lead_id)
    if lead is None or lead.workspace_id != workspace_id:
        return AlertResult(fired=False, channel=None, reason="not_configured")

    ws = db.get(Workspace, workspace_id)
    if ws is None:
        return AlertResult(fired=False, channel=None, reason="not_configured")

    if _recent_alert(db, workspace_id, lead_id, alert_type):
        return AlertResult(fired=False, channel=None, reason="dedup")

    body = _build_body(alert_type, lead)
    channels_fired: list[str] = []

    # SMS to owner (primary). Respect owner quiet hours — if it's 2am
    # where the owner is, we skip SMS and fall back to Slack only.
    if ws.owner_phone:
        if is_within_owner_window(ws.owner_timezone):
            result = send_sms(to_e164=ws.owner_phone, body=body)
            if result.status in ("sent", "demo"):
                db.add(OwnerAlert(
                    workspace_id=workspace_id, lead_id=lead_id, campaign_id=lead.campaign_id,
                    alert_type=alert_type, channel="sms", body=body,
                    twilio_sid=result.sid, status="sent",
                ))
                channels_fired.append("sms")
            else:
                db.add(OwnerAlert(
                    workspace_id=workspace_id, lead_id=lead_id, campaign_id=lead.campaign_id,
                    alert_type=alert_type, channel="sms", body=body,
                    status="failed",
                ))
        else:
            db.add(OwnerAlert(
                workspace_id=workspace_id, lead_id=lead_id, campaign_id=lead.campaign_id,
                alert_type=alert_type, channel="sms", body=body,
                status="skipped",
            ))

    # Slack (parallel channel; always fires even during owner quiet hours
    # because Slack notifications respect the user's own mute settings).
    if ws.slack_webhook_url:
        ok = _slack_post(ws.slack_webhook_url, body)
        db.add(OwnerAlert(
            workspace_id=workspace_id, lead_id=lead_id, campaign_id=lead.campaign_id,
            alert_type=alert_type, channel="slack", body=body,
            status="sent" if ok else "failed",
        ))
        if ok:
            channels_fired.append("slack")

    db.commit()

    if channels_fired:
        return AlertResult(fired=True, channel=",".join(channels_fired), reason="sent")
    if not ws.owner_phone and not ws.slack_webhook_url:
        return AlertResult(fired=False, channel=None, reason="not_configured")
    # Phone configured but we skipped it (quiet hours), and no slack fallback.
    return AlertResult(fired=False, channel=None, reason="quiet_hours")
