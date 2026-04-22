# Why this exists: the drip. Every tick, find messages whose scheduled_for
# has arrived for leads still active, send via Twilio (or no-op in DEMO),
# mark sent, advance lead state. Respects quiet hours per lead timezone.
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.orm import Lead, Message
from app.services.compliance import can_send, record_event
from app.services.quiet_hours import is_within_quiet_window
from app.services.twilio_client import send_sms
from app.utils.logger import get_logger

log = get_logger("scheduler")

_ACTIVE_STATES = ("queued", "contacted", "replied_hot")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def tick(db: Optional[Session] = None) -> dict:
    """Send everything due. Returns a summary for observability + tests."""
    owned = False
    if db is None:
        db = SessionLocal()
        owned = True
    try:
        now = _now()
        due = db.scalars(
            select(Message)
            .join(Lead, Lead.id == Message.lead_id)
            .where(
                Message.status == "pending",
                Message.direction == "out",
                Message.scheduled_for <= now,
                Lead.state.in_(_ACTIVE_STATES),
            )
            .order_by(Message.scheduled_for.asc())
        ).all()

        sent = 0
        skipped_quiet = 0
        blocked_compliance = 0
        failed = 0
        for m in due:
            lead = db.get(Lead, m.lead_id)
            if lead is None or lead.state not in _ACTIVE_STATES:
                m.status = "cancelled"
                continue
            if not lead.phone:
                m.status = "failed"
                failed += 1
                continue
            if not is_within_quiet_window(lead.phone):
                skipped_quiet += 1
                continue  # leave pending; next tick will retry

            # TCPA gate — opt-out, DNC, frequency cap.
            decision = can_send(db, lead.phone, m.workspace_id)
            if not decision.allowed:
                m.status = "cancelled"
                blocked_compliance += 1
                record_event(
                    db,
                    event_type=decision.reason,
                    workspace_id=m.workspace_id,
                    phone=lead.phone,
                    lead_id=lead.id,
                    campaign_id=m.campaign_id,
                    meta={"message_id": m.id, "step": m.step, "detail": decision.detail},
                )
                continue

            result = send_sms(to_e164=lead.phone, body=m.body)
            if result.status == "failed":
                m.status = "failed"
                failed += 1
                continue
            m.status = "sent"
            m.sent_at = _now()
            m.twilio_sid = result.sid
            if lead.state == "queued":
                lead.state = "contacted"
            sent += 1

        db.commit()
        return {
            "sent": sent,
            "skipped_quiet": skipped_quiet,
            "blocked_compliance": blocked_compliance,
            "failed": failed,
            "due": len(due),
        }
    finally:
        if owned:
            db.close()


_scheduler: Optional[BackgroundScheduler] = None


def start_scheduler(interval_minutes: int = 15) -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(tick, "interval", minutes=interval_minutes, id="revival_tick", replace_existing=True)
    _scheduler.start()
    log.info("scheduler started — tick every %d min", interval_minutes)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler stopped")
