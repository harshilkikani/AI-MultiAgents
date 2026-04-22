# Why this exists: campaigns CRUD. Kept thin — all state lives in ORM.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Campaign, Lead
from app.models.schemas import VERTICALS, CampaignCreate, CampaignOut, CampaignUpdate
from app.services.audit import record as audit_record

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _ws(request: Request) -> int:
    # Single-tenant in v0; M7 replaces this with auth middleware.
    return getattr(request.state, "workspace_id", 1)


def _to_out(c: Campaign, lead_count: int) -> CampaignOut:
    return CampaignOut(
        id=c.id, workspace_id=c.workspace_id, name=c.name, vertical=c.vertical,
        avg_ticket=c.avg_ticket, calendly_url=c.calendly_url,
        tone_notes=c.tone_notes,
        created_at=c.created_at, launched_at=c.launched_at,
        paid=bool(c.paid), trial_leads_used=c.trial_leads_used,
        paused=bool(c.paused), paused_at=c.paused_at,
        lead_count=lead_count,
    )


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate, request: Request, db: Session = Depends(get_db)) -> CampaignOut:
    if payload.vertical not in VERTICALS:
        raise HTTPException(status_code=422, detail=f"vertical must be one of {VERTICALS}")
    c = Campaign(
        workspace_id=_ws(request),
        name=payload.name,
        vertical=payload.vertical,
        avg_ticket=payload.avg_ticket,
        calendly_url=payload.calendly_url,
        tone_notes=payload.tone_notes,
    )
    db.add(c)
    db.flush()  # get c.id before audit insert
    audit_record(
        db,
        workspace_id=c.workspace_id, campaign_id=c.id,
        event_type="campaign.created", actor_type="user",
        actor_id=str(getattr(request.state, "external_id", None) or ""),
        summary=f"Campaign '{c.name}' created ({c.vertical})",
        after={"name": c.name, "vertical": c.vertical, "avg_ticket": c.avg_ticket},
    )
    db.commit()
    db.refresh(c)
    return _to_out(c, lead_count=0)


@router.get("", response_model=list[CampaignOut])
def list_campaigns(request: Request, db: Session = Depends(get_db)) -> list[CampaignOut]:
    ws = _ws(request)
    rows = db.execute(
        select(Campaign, func.count(Lead.id))
        .outerjoin(Lead, Lead.campaign_id == Campaign.id)
        .where(Campaign.workspace_id == ws)
        .group_by(Campaign.id)
        .order_by(Campaign.created_at.desc())
    ).all()
    return [_to_out(c, int(n or 0)) for c, n in rows]


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, request: Request, db: Session = Depends(get_db)) -> CampaignOut:
    ws = _ws(request)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")
    n = db.scalar(select(func.count(Lead.id)).where(Lead.campaign_id == c.id))
    return _to_out(c, int(n or 0))


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> CampaignOut:
    ws = _ws(request)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")
    if payload.name is not None:
        c.name = payload.name.strip() or c.name
    if payload.avg_ticket is not None:
        c.avg_ticket = float(payload.avg_ticket)
    if payload.calendly_url is not None:
        c.calendly_url = payload.calendly_url.strip() or None
    if payload.tone_notes is not None:
        c.tone_notes = payload.tone_notes.strip() or None
    db.commit()
    db.refresh(c)
    return _to_out(c, _lead_count(db, c.id))


def _lead_count(db: Session, campaign_id: int) -> int:
    return int(db.scalar(select(func.count(Lead.id)).where(Lead.campaign_id == campaign_id)) or 0)


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
def pause_campaign(campaign_id: int, request: Request, db: Session = Depends(get_db)) -> CampaignOut:
    from datetime import UTC, datetime
    ws = _ws(request)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")
    if not c.paused:
        c.paused = 1
        c.paused_at = datetime.now(UTC).replace(tzinfo=None)
        audit_record(
            db,
            workspace_id=ws, campaign_id=c.id,
            event_type="campaign.paused", actor_type="user",
            actor_id=str(getattr(request.state, "external_id", None) or ""),
            summary="Campaign paused",
        )
        db.commit()
        db.refresh(c)
    return _to_out(c, _lead_count(db, c.id))


@router.post("/{campaign_id}/resume", response_model=CampaignOut)
def resume_campaign(campaign_id: int, request: Request, db: Session = Depends(get_db)) -> CampaignOut:
    ws = _ws(request)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")
    if c.paused:
        c.paused = 0
        c.paused_at = None
        audit_record(
            db,
            workspace_id=ws, campaign_id=c.id,
            event_type="campaign.resumed", actor_type="user",
            actor_id=str(getattr(request.state, "external_id", None) or ""),
            summary="Campaign resumed",
        )
        db.commit()
        db.refresh(c)
    return _to_out(c, _lead_count(db, c.id))
