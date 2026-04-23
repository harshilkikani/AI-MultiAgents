# Why this exists: login / logout endpoints. In DEMO_MODE these return
# stub tokens so the UI has a working auth flow without a Supabase project.
from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth import _demo_context, resolve_auth_context
from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("routes.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str  # lenient — Supabase validates on its end
    redirect_to: Optional[str] = None


@router.post("/login")
def request_magic_link(payload: LoginRequest, db: Session = Depends(get_db)):
    """Start a magic-link login. In DEMO_MODE this short-circuits with a
    stub token so the UI has a working auth flow without a live Supabase
    project. In real mode it delegates to Supabase's REST OTP endpoint."""
    settings = get_settings()

    if settings.demo_mode:
        # Synthesize a token the backend will accept (demo- prefix triggers
        # the DEMO path in resolve_auth_context).
        ctx = _demo_context(db, requested_ws=None)
        token = f"demo-{ctx.external_id}-{int(time.time())}"
        return {
            "mode": "demo",
            "message": "DEMO_MODE: here's a stub session — no email sent.",
            "token": token,
            "user": {"external_id": ctx.external_id, "email": ctx.email, "workspace_id": ctx.workspace_id},
        }

    # Real mode: call Supabase's /auth/v1/otp endpoint.
    if not (settings.supabase_url and settings.supabase_anon_key):
        raise HTTPException(status_code=500, detail="SUPABASE_URL / SUPABASE_ANON_KEY not configured")

    import httpx
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/otp"
    data = {"email": payload.email}
    if payload.redirect_to:
        data["options"] = {"emailRedirectTo": payload.redirect_to}  # type: ignore[assignment]
    headers = {
        "apikey": settings.supabase_anon_key,
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post(url, json=data, headers=headers, timeout=10.0)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"supabase request failed: {e}")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"supabase rejected: {r.text}")
    return {"mode": "real", "message": "Magic link sent — check your email."}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("Authorization")
    ws_hdr = request.headers.get("X-Workspace-Id")
    try:
        requested = int(ws_hdr) if ws_hdr else None
    except ValueError:
        requested = None
    ctx = resolve_auth_context(db, authorization_header=auth, requested_workspace=requested)
    if ctx is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return {
        "user": {"external_id": ctx.external_id, "email": ctx.email},
        "workspace_id": ctx.workspace_id,
        "is_demo": ctx.is_demo,
    }


@router.post("/logout")
def logout():
    """Stateless logout — clients drop the token. Kept as an endpoint so
    the UI has a canonical call to make."""
    return {"ok": True}
