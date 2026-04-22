# Why this exists: owner-facing endpoints for CRM integrations. Today
# Jobber only; ServiceTitan + Housecall Pro follow the same shape.
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import JobberConnection
from app.services import jobber as jobber_svc
from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("routes.integrations")

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _ws(request: Request) -> int:
    return getattr(request.state, "workspace_id", 1)


def _conn_to_out(conn: Optional[JobberConnection]) -> dict:
    if not conn or conn.status != "active":
        return {"connected": False}
    return {
        "connected": True,
        "account_name": conn.account_name,
        "scopes": conn.scopes,
        "connected_at": conn.connected_at.isoformat(),
        "last_synced_at": conn.last_synced_at.isoformat() if conn.last_synced_at else None,
        "last_sync_stats": conn.last_sync_stats,
    }


@router.get("/jobber")
def jobber_status(request: Request, db: Session = Depends(get_db)):
    ws = _ws(request)
    conn = db.scalars(select(JobberConnection).where(JobberConnection.workspace_id == ws)).first()
    return _conn_to_out(conn)


@router.post("/jobber/connect")
def jobber_connect(request: Request, db: Session = Depends(get_db)):
    """Begin OAuth flow. In DEMO_MODE we short-circuit and hand back a
    fake callback URL that produces an immediate active connection."""
    settings = get_settings()
    ws = _ws(request)
    state = secrets.token_urlsafe(24)

    if settings.demo_mode:
        # Short-circuit: emit a callback URL the frontend can POST to
        # (a real browser-flow wouldn't call it this way, but demo UI does).
        return {
            "mode": "demo",
            "authorize_url": f"/api/integrations/jobber/callback?code=DEMO-{state}&state={state}",
            "state": state,
        }

    return {"mode": "real", "authorize_url": jobber_svc.build_authorize_url(state), "state": state}


@router.get("/jobber/callback")
def jobber_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
):
    """OAuth callback. In DEMO_MODE, `code` is anything — we'll mint a
    fake token. Real mode swaps the code with Jobber."""
    ws = _ws(request) if request is not None else 1
    tokens = jobber_svc.exchange_code_for_token(code)
    conn = jobber_svc.save_connection(db, workspace_id=ws, tokens=tokens)
    return _conn_to_out(conn)


@router.post("/jobber/disconnect")
def jobber_disconnect(request: Request, db: Session = Depends(get_db)):
    ws = _ws(request)
    ok = jobber_svc.disconnect(db, workspace_id=ws)
    if not ok:
        raise HTTPException(status_code=404, detail="no active jobber connection")
    return {"ok": True}


@router.post("/jobber/sync")
def jobber_sync(
    request: Request,
    campaign_id: int = Query(...),
    cutoff_days: int = Query(180, ge=30, le=1825),
    db: Session = Depends(get_db),
):
    ws = _ws(request)
    try:
        result = jobber_svc.sync_cold_leads(
            db, workspace_id=ws, campaign_id=campaign_id, cutoff_days=cutoff_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("jobber sync failed")
        raise HTTPException(status_code=502, detail=f"jobber sync failed: {e}")
    return {
        "ok": True,
        "pulled": result.pulled,
        "inserted": result.inserted,
        "already_present": result.already_present,
        "skipped": result.skipped,
    }
