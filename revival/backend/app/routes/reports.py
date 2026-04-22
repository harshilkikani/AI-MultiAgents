# Why this exists: data for the dashboard + ROI-report pages.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Campaign, Lead, Message
from app.models.schemas import LeadOut
from app.services.roi import compute_stats, stats_as_dict

router = APIRouter(prefix="/api/campaigns", tags=["reports"])


def _ws(request: Request) -> int:
    return getattr(request.state, "workspace_id", 1)


@router.get("/{campaign_id}/stats")
def campaign_stats(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    ws = _ws(request)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")
    return stats_as_dict(compute_stats(db, c))


@router.get("/{campaign_id}/leads/{lead_id}/messages")
def lead_messages(campaign_id: int, lead_id: int, request: Request, db: Session = Depends(get_db)):
    ws = _ws(request)
    lead = db.get(Lead, lead_id)
    if not lead or lead.workspace_id != ws or lead.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="lead not found")
    rows = db.scalars(
        select(Message)
        .where(Message.lead_id == lead_id)
        .order_by(Message.id.asc())
    ).all()
    return {
        "lead": LeadOut.model_validate(lead).model_dump(),
        "messages": [
            {
                "id": m.id,
                "step": m.step,
                "direction": m.direction,
                "body": m.body,
                "scheduled_for": m.scheduled_for.isoformat() if m.scheduled_for else None,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "status": m.status,
            }
            for m in rows
        ],
    }
