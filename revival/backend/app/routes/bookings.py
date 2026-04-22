# Why this exists: Calendly webhook receiver. When a replied_hot lead
# books on the shop's Calendly page, this flips them to `booked`.
#
# Calendly's real webhook payload is shaped like:
#   { "event": "invitee.created",
#     "payload": { "invitee": { "email": "...", "text_reminder_number": "+1..." },
#                  "event":   { "start_time": "..." } } }
#
# In v0 we accept a flexible payload: any of lead_id, phone, or email maps
# the booking back to a lead. Signature verification is deferred — add the
# calendly webhook-signing-key check before pointing real Calendly at this.
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Lead
from app.services.webhook_auth import verify_calendly_request
from app.utils.logger import get_logger

log = get_logger("bookings")

router = APIRouter(prefix="/webhooks", tags=["bookings"])


def _extract_ids(payload: dict) -> dict:
    """Normalize the various Calendly-ish payload shapes we might receive."""
    # Flat top-level
    lead_id = payload.get("lead_id")
    phone = payload.get("phone") or payload.get("From") or payload.get("text_reminder_number")
    email = payload.get("email")

    # Nested under 'payload'
    inner = payload.get("payload") or {}
    invitee = inner.get("invitee") or {}
    phone = phone or invitee.get("text_reminder_number")
    email = email or invitee.get("email")

    return {"lead_id": lead_id, "phone": phone, "email": (email or "").lower() if email else None}


@router.post("/calendly")
async def calendly_webhook(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    if not await verify_calendly_request(request, body_bytes):
        raise HTTPException(status_code=403, detail="invalid calendly signature")
    try:
        payload = __import__("json").loads(body_bytes.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    ids = _extract_ids(payload)
    lead: Optional[Lead] = None

    if ids["lead_id"]:
        lead = db.get(Lead, int(ids["lead_id"]))
    if lead is None and ids["phone"]:
        lead = db.scalars(
            select(Lead).where(Lead.phone == ids["phone"]).order_by(Lead.id.desc())
        ).first()
    if lead is None and ids["email"]:
        lead = db.scalars(
            select(Lead).where(Lead.email == ids["email"]).order_by(Lead.id.desc())
        ).first()

    if lead is None:
        log.info("calendly webhook — no matching lead for %s", ids)
        return {"ok": True, "matched": False}

    # Only advance hot → booked; don't reopen a cancelled/opted_out lead.
    if lead.state in ("replied_hot", "contacted"):
        lead.state = "booked"
        db.commit()
        return {"ok": True, "matched": True, "lead_id": lead.id, "state": lead.state}

    return {"ok": True, "matched": True, "lead_id": lead.id, "state": lead.state, "no_change": True}
