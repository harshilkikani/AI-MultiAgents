# Why this exists: owner-facing endpoints for the TCPA paper trail.
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import ComplianceEvent, Lead, OptOut
from app.services.compliance import opt_out

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class ManualOptOut(BaseModel):
    phone: str
    reason: Optional[str] = None


def _ws(request: Request) -> int:
    return getattr(request.state, "workspace_id", 1)


@router.post("/opt-outs", status_code=201)
def manual_opt_out(
    payload: ManualOptOut,
    request: Request,
    db: Session = Depends(get_db),
):
    """Owner marks a phone number as opted out by hand (e.g. customer
    called and asked to be removed, form submission, etc.)."""
    ws = _ws(request)
    phone = payload.phone.strip()
    if not phone.startswith("+"):
        raise HTTPException(status_code=422, detail="phone must be E.164 (leading + and country code)")

    # Cancel any outstanding pending outbound for this phone in this workspace.
    from app.models.orm import Message
    phones_leads = db.scalars(
        select(Lead.id).where(Lead.workspace_id == ws, Lead.phone == phone)
    ).all()
    if phones_leads:
        db.query(Message).filter(
            Message.lead_id.in_(phones_leads),
            Message.status == "pending",
        ).update({"status": "cancelled"}, synchronize_session=False)
        db.query(Lead).filter(Lead.id.in_(phones_leads)).update(
            {"state": "opted_out"}, synchronize_session=False,
        )

    opt_out(
        db, phone=phone, workspace_id=ws, source="manual",
        proof_body=payload.reason,
    )
    db.commit()
    return {"ok": True, "phone": phone}


@router.get("/opt-outs")
def list_opt_outs(request: Request, db: Session = Depends(get_db)):
    ws = _ws(request)
    rows = db.scalars(
        select(OptOut).where(OptOut.workspace_id == ws).order_by(OptOut.opted_out_at.desc())
    ).all()
    return [
        {
            "phone": r.phone,
            "opted_out_at": r.opted_out_at.isoformat(),
            "source": r.source,
            "proof_body": r.proof_body,
            "proof_message_sid": r.proof_message_sid,
        }
        for r in rows
    ]


@router.get("/events")
def list_events(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 100,
    event_type: Optional[str] = None,
):
    ws = _ws(request)
    q = select(ComplianceEvent).where(ComplianceEvent.workspace_id == ws)
    if event_type:
        q = q.where(ComplianceEvent.event_type == event_type)
    rows = db.scalars(q.order_by(ComplianceEvent.created_at.desc()).limit(min(limit, 1000))).all()
    return [
        {
            "id": r.id, "event_type": r.event_type, "phone": r.phone,
            "lead_id": r.lead_id, "campaign_id": r.campaign_id,
            "created_at": r.created_at.isoformat(),
            "body": r.body, "message_sid": r.message_sid, "meta": r.meta,
        }
        for r in rows
    ]
