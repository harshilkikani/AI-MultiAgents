# Why this exists: CSV upload endpoint + per-campaign lead listing.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Campaign, Lead
from app.models.schemas import LeadOut, UploadResult
from app.services.csv_ingest import parse_csv

router = APIRouter(prefix="/api/campaigns", tags=["leads"])

MAX_CSV_BYTES = 10 * 1024 * 1024  # 10 MB cap — big enough for 50k leads, small enough to reject a dropped wrong file


def _ws(request: Request) -> int:
    return getattr(request.state, "workspace_id", 1)


@router.post("/{campaign_id}/leads/upload", response_model=UploadResult)
async def upload_leads(
    campaign_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResult:
    ws = _ws(request)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="file must be a .csv")

    content = await file.read()
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail=f"csv too large (> {MAX_CSV_BYTES // 1024 // 1024} MB)")

    leads, skipped = parse_csv(content)
    inserted = 0
    for ld in leads:
        db.add(Lead(
            workspace_id=ws,
            campaign_id=c.id,
            name=ld.name, phone=ld.phone, email=ld.email,
            source=ld.source, last_contact=ld.last_contact, notes=ld.notes,
        ))
        inserted += 1
    db.commit()

    preview_rows = db.scalars(
        select(Lead).where(Lead.campaign_id == c.id).order_by(Lead.id.desc()).limit(5)
    ).all()
    preview = [LeadOut.model_validate(l) for l in preview_rows][::-1]

    return UploadResult(
        campaign_id=c.id,
        inserted=inserted,
        skipped=len(skipped),
        skipped_reasons=skipped[:20],  # don't echo 10k reasons
        preview=preview,
    )


@router.get("/{campaign_id}/leads", response_model=list[LeadOut])
def list_leads(
    campaign_id: int,
    request: Request,
    state: str | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
) -> list[LeadOut]:
    ws = _ws(request)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")

    q = select(Lead).where(Lead.campaign_id == c.id)
    if state:
        q = q.where(Lead.state == state)
    q = q.order_by(Lead.id.asc()).limit(min(limit, 2000))
    rows = db.scalars(q).all()
    return [LeadOut.model_validate(l) for l in rows]
