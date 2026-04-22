# Why this exists: expose the revival pipeline as a single endpoint.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.revival_pipeline import generate_for_campaign

router = APIRouter(prefix="/api/campaigns", tags=["generate"])


@router.post("/{campaign_id}/generate")
def generate(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    ws = getattr(request.state, "workspace_id", 1)
    try:
        return generate_for_campaign(db=db, campaign_id=campaign_id, workspace_id=ws)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
