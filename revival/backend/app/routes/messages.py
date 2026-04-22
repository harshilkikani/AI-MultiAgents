# Why this exists: manual send trigger (for UI buttons + M4 scheduler) and
# the Twilio inbound webhook. Calendly webhook lives in the bookings
# router (M5) to keep concerns separate.
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Campaign, Lead, Message
from app.services.alerts import fire_alert
from app.services.compliance import can_send, opt_out, record_event
from app.services.reply_classifier import classify_reply
from app.services.twilio_client import send_sms
from app.services.webhook_auth import verify_twilio_request
from app.utils.logger import get_logger


def _auto_reply_for_hot(lead: Lead, campaign: Campaign) -> Optional[str]:
    """Compose the 'yes, here's the calendar link' auto-reply. Keeps tone
    aligned with the drip — no corporate boilerplate."""
    name = (lead.name or "there").split()[0]
    if campaign and campaign.calendly_url:
        return (
            f"Awesome, {name} — here's my calendar, grab the slot that works: "
            f"{campaign.calendly_url}"
        )
    # No Calendly configured yet: promise a human follow-up so the lead
    # doesn't go cold while the shop owner wires up their link.
    return (
        f"Awesome, {name} — I'll ring you back within the hour to lock a time. "
        "If you don't hear from me, text back this number."
    )

log = get_logger("routes.messages")

router = APIRouter(tags=["messages"])


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@router.post("/api/messages/{message_id}/send")
def manual_send(message_id: int, request: Request, db: Session = Depends(get_db)):
    ws = getattr(request.state, "workspace_id", 1)
    m = db.get(Message, message_id)
    if not m or m.workspace_id != ws:
        raise HTTPException(status_code=404, detail="message not found")
    if m.direction != "out":
        raise HTTPException(status_code=400, detail="only outbound messages can be sent")
    if m.status == "sent":
        return {"message_id": m.id, "status": "already_sent", "sid": m.twilio_sid}

    lead = db.get(Lead, m.lead_id)
    if lead is None or lead.state in ("opted_out", "replied_no", "dead"):
        m.status = "failed"
        db.commit()
        raise HTTPException(status_code=400, detail=f"lead is in terminal state: {lead.state if lead else 'missing'}")

    if not lead.phone:
        m.status = "failed"
        db.commit()
        raise HTTPException(status_code=400, detail="lead has no phone number")

    decision = can_send(db, lead.phone, m.workspace_id)
    if not decision.allowed:
        m.status = "cancelled"
        record_event(
            db,
            event_type=decision.reason,
            workspace_id=m.workspace_id,
            phone=lead.phone,
            lead_id=lead.id,
            campaign_id=m.campaign_id,
            meta={"message_id": m.id, "detail": decision.detail, "via": "manual_send"},
        )
        db.commit()
        raise HTTPException(status_code=409, detail=f"blocked: {decision.reason} — {decision.detail}")

    result = send_sms(to_e164=lead.phone, body=m.body)
    if result.status == "failed":
        m.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=f"send failed: {result.error}")

    m.status = "sent"
    m.sent_at = _now()
    m.twilio_sid = result.sid
    if lead.state == "queued":
        lead.state = "contacted"
    db.commit()
    return {"message_id": m.id, "status": result.status, "sid": result.sid}


@router.post("/webhooks/twilio/inbound")
async def twilio_inbound(
    request: Request,
    From: str = Form(...),          # E.164 sender
    Body: str = Form(""),
    MessageSid: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Twilio webhook. Finds the most recent lead matching `From`, classifies
    the reply, transitions state, and replies (Calendly auto-reply on hot)."""
    # M12 — Twilio signature verification. Blocks spoofed inbound replies
    # that could poison opt-out records or trigger fake booking links.
    if not await verify_twilio_request(request):
        log.warning("twilio: signature check failed for inbound from %s", From)
        raise HTTPException(status_code=403, detail="invalid twilio signature")

    intent = classify_reply(Body)

    # Find the most recently-contacted lead on this phone.
    lead = db.scalars(
        select(Lead)
        .where(Lead.phone == From, Lead.state.in_(("queued", "contacted", "replied_hot")))
        .order_by(Lead.id.desc())
    ).first()

    if lead is None:
        log.info("inbound from %s with no matching active lead; dropping", From)
        return Response(content="<Response/>", media_type="application/xml")

    # Persist the inbound message.
    inbound = Message(
        workspace_id=lead.workspace_id,
        lead_id=lead.id,
        campaign_id=lead.campaign_id,
        step=-1,
        body=Body or "",
        direction="in",
        sent_at=_now(),
        status="received",
        twilio_sid=MessageSid,
    )
    db.add(inbound)

    # State transitions.
    auto_reply_body: Optional[str] = None
    if intent == "stop":
        lead.state = "opted_out"
        # Write to the global opt_outs table so NO future campaign in this
        # workspace can ever SMS this phone again (TCPA hard rule).
        if lead.phone:
            opt_out(
                db,
                phone=lead.phone,
                workspace_id=lead.workspace_id,
                source="sms_reply",
                proof_body=Body,
                proof_message_sid=MessageSid,
                lead_id=lead.id,
                campaign_id=lead.campaign_id,
            )
    elif intent == "yes":
        lead.state = "replied_hot"
        campaign = db.get(Campaign, lead.campaign_id)
        auto_reply_body = _auto_reply_for_hot(lead, campaign)
    elif intent == "no":
        lead.state = "replied_no"
    elif intent == "maybe":
        if lead.state == "queued":
            lead.state = "contacted"
        # otherwise leave as contacted so the drip continues
    else:
        # 'other' — still count as engagement for trial_leads_used metering
        if lead.state == "queued":
            lead.state = "contacted"

    # Cancel any future pending messages for terminal states.
    if lead.state in ("opted_out", "replied_no"):
        db.query(Message).filter(
            Message.lead_id == lead.id,
            Message.status == "pending",
        ).update({"status": "cancelled"}, synchronize_session=False)

    # On "yes" → send the booking link as a separate outbound SMS so it
    # lives in the message thread history. Must still respect compliance
    # (opt-out / DNC / freq-cap) — a bot-spoofing attacker can't trick the
    # system into sending to a blocked number via a forged "yes".
    if auto_reply_body and lead.phone:
        decision = can_send(db, lead.phone, lead.workspace_id)
        if not decision.allowed:
            record_event(
                db,
                event_type=decision.reason,
                workspace_id=lead.workspace_id,
                phone=lead.phone,
                lead_id=lead.id,
                campaign_id=lead.campaign_id,
                meta={"detail": decision.detail, "via": "auto_reply"},
            )
            auto_reply_body = None  # skip the send but keep state transition
    if auto_reply_body and lead.phone:
        result = send_sms(to_e164=lead.phone, body=auto_reply_body)
        reply_msg = Message(
            workspace_id=lead.workspace_id,
            lead_id=lead.id,
            campaign_id=lead.campaign_id,
            step=99,  # sentinel = auto-reply, not a drip step
            body=auto_reply_body,
            direction="out",
            sent_at=_now() if result.status in ("sent", "demo") else None,
            status="sent" if result.status in ("sent", "demo") else "failed",
            twilio_sid=result.sid,
        )
        db.add(reply_msg)
        # Cancel remaining drip messages — we've pivoted to booking.
        db.query(Message).filter(
            Message.lead_id == lead.id,
            Message.status == "pending",
            Message.direction == "out",
            Message.step < 99,
        ).update({"status": "cancelled"}, synchronize_session=False)

    db.commit()

    # M16 — buzz the shop owner. Happens AFTER commit so the replied_hot
    # state is queryable when the alert path runs. Alert errors must not
    # surface to Twilio — they silent-fail and log.
    if intent == "yes":
        try:
            fire_alert(
                db,
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                alert_type="replied_hot",
            )
        except Exception as e:
            log.exception("owner alert (replied_hot) failed: %s", e)

    # Return empty TwiML so Twilio doesn't echo anything.
    return Response(content="<Response/>", media_type="application/xml")
