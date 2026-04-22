# Why this exists: public demo endpoints. Frontends call /api/demo/info to
# discover the demo workspace + campaign id, then render the normal
# CampaignDetail/RoiReport pages scoped to that workspace.
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Campaign, Workspace
from app.services.demo_seed import DEMO_WS_ID, build_demo

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/info")
def demo_info(db: Session = Depends(get_db)):
    """Return the demo workspace id + most-recent campaign id. If the demo
    hasn't been seeded yet, return 404 so the UI can prompt a reset."""
    ws = db.get(Workspace, DEMO_WS_ID)
    if ws is None:
        return {"seeded": False}
    c = db.scalars(
        select(Campaign)
        .where(Campaign.workspace_id == DEMO_WS_ID)
        .order_by(Campaign.id.desc())
    ).first()
    return {
        "seeded": c is not None,
        "workspace_id": DEMO_WS_ID,
        "workspace_name": ws.name,
        "campaign_id": c.id if c else None,
    }


@router.post("/reset")
def demo_reset(db: Session = Depends(get_db)):
    """Rebuild the demo workspace. Safe to call from a sales-demo UI
    button — whole operation is a few seconds in DEMO_MODE."""
    summary = build_demo(db)
    return {"ok": True, **summary}
