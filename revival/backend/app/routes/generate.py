# Why this exists: expose the revival pipeline as a single endpoint.
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Campaign, Lead
from app.services.revival_pipeline import _generate_one, generate_for_campaign

router = APIRouter(prefix="/api/campaigns", tags=["generate"])


@router.post("/{campaign_id}/generate")
def generate(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    ws = getattr(request.state, "workspace_id", 1)
    try:
        return generate_for_campaign(db=db, campaign_id=campaign_id, workspace_id=ws)
    except PermissionError as e:
        raise HTTPException(status_code=402, detail=str(e))  # 402 = payment required
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{campaign_id}/sample-generate")
def sample_generate(
    campaign_id: int,
    request: Request,
    n: int = 3,
    db: Session = Depends(get_db),
):
    """Generate sample messages for N leads from the campaign WITHOUT
    persisting or burning the trial allowance. Lets the owner eyeball
    quality before spending Claude tokens on hundreds of messages."""
    ws = getattr(request.state, "workspace_id", 1)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")

    n = max(1, min(n, 5))
    leads = db.scalars(
        select(Lead).where(Lead.campaign_id == c.id, Lead.workspace_id == ws)
    ).all()
    if not leads:
        raise HTTPException(status_code=400, detail="campaign has no leads yet; upload a CSV first")

    picked = random.sample(leads, k=min(n, len(leads)))
    samples = []
    for lead in picked:
        out = _generate_one(lead, avg_ticket=c.avg_ticket)
        samples.append({
            "lead": {
                "id": lead.id, "name": lead.name, "phone": lead.phone,
                "source": lead.source,
                "last_contact": lead.last_contact.isoformat() if lead.last_contact else None,
            },
            "initial_msg": out["initial_msg"],
            "drip_msgs": out["drip_msgs"],
            "urgency_score": out["urgency_score"],
            "best_time_of_day": out["best_time_of_day"],
            "strategy_note": out.get("strategy_note", ""),
        })
    return {"campaign_id": c.id, "vertical": c.vertical, "samples": samples}
