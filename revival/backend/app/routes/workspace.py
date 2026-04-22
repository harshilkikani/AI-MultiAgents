# Why this exists: owner-facing workspace settings (alert routing).
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Workspace

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class WorkspaceSettings(BaseModel):
    name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    owner_timezone: Optional[str] = None
    slack_webhook_url: Optional[str] = None


def _ws(request: Request) -> int:
    return getattr(request.state, "workspace_id", 1)


def _to_out(w: Workspace) -> dict:
    return {
        "id": w.id, "name": w.name,
        "owner_phone": w.owner_phone,
        "owner_email": w.owner_email,
        "owner_timezone": w.owner_timezone,
        "slack_webhook_url": w.slack_webhook_url,
        "trial_leads_used": w.trial_leads_used,
    }


@router.get("")
def get_workspace(request: Request, db: Session = Depends(get_db)):
    ws_id = _ws(request)
    w = db.get(Workspace, ws_id)
    if not w:
        raise HTTPException(status_code=404, detail="workspace not found")
    return _to_out(w)


@router.patch("")
def update_workspace(
    payload: WorkspaceSettings,
    request: Request,
    db: Session = Depends(get_db),
):
    ws_id = _ws(request)
    w = db.get(Workspace, ws_id)
    if not w:
        raise HTTPException(status_code=404, detail="workspace not found")

    # E.164 check on owner phone — loud and clear so owners don't paste
    # "(555) 123-4567" and wonder why alerts never fire.
    if payload.owner_phone is not None:
        raw = payload.owner_phone.strip()
        if raw and not raw.startswith("+"):
            raise HTTPException(status_code=422, detail="owner_phone must be E.164 (leading + and country code)")
        w.owner_phone = raw or None

    if payload.name is not None:
        w.name = payload.name.strip() or w.name
    if payload.owner_email is not None:
        w.owner_email = payload.owner_email.strip() or None
    if payload.owner_timezone is not None:
        tz = payload.owner_timezone.strip()
        if tz:
            # Validate against zoneinfo so typos (e.g., "America/Pheonix")
            # fail loudly instead of silently reverting to ET at send time.
            from zoneinfo import ZoneInfo
            try:
                ZoneInfo(tz)
            except Exception:
                raise HTTPException(status_code=422, detail=f"unknown timezone: {tz!r}")
            w.owner_timezone = tz
        else:
            w.owner_timezone = None
    if payload.slack_webhook_url is not None:
        url = payload.slack_webhook_url.strip()
        if url and not url.startswith("https://hooks.slack.com/"):
            raise HTTPException(status_code=422, detail="slack_webhook_url must be a hooks.slack.com URL")
        w.slack_webhook_url = url or None

    db.commit()
    db.refresh(w)
    return _to_out(w)
