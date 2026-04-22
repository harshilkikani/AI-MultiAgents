# Why this exists: owner-facing audit log. CampaignDetail's Activity tab
# reads this; regulators ask "did you text my customer?" and we point at
# the rendered list.
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import AuditEvent, Campaign

router = APIRouter(prefix="/api/campaigns", tags=["audit"])


def _ws(request: Request) -> int:
    return getattr(request.state, "workspace_id", 1)


@router.get("/{campaign_id}/audit")
def campaign_audit(
    campaign_id: int,
    request: Request,
    event_type: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    ws = _ws(request)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")

    q = select(AuditEvent).where(
        AuditEvent.workspace_id == ws,
        AuditEvent.campaign_id == campaign_id,
    )
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    rows = db.scalars(q.order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": r.id, "event_type": r.event_type, "summary": r.summary,
            "actor_type": r.actor_type, "actor_id": r.actor_id,
            "lead_id": r.lead_id,
            "created_at": r.created_at.isoformat(),
            "before": r.before, "after": r.after, "meta": r.meta,
        }
        for r in rows
    ]
