# Why this exists: Checkout session creation + Stripe webhook.
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import Campaign
from app.services.billing import (
    MONTHLY_PLAN,
    ONE_SHOT_PLAN,
    create_checkout_session,
    mark_campaign_paid,
)
from app.services.webhook_auth import verify_stripe_event
from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("routes.billing")

router = APIRouter(tags=["billing"])


@router.post("/api/campaigns/{campaign_id}/checkout")
def create_checkout(
    campaign_id: int,
    request: Request,
    plan: str = ONE_SHOT_PLAN,
    db: Session = Depends(get_db),
):
    ws = getattr(request.state, "workspace_id", 1)
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != ws:
        raise HTTPException(status_code=404, detail="campaign not found")
    if plan not in (ONE_SHOT_PLAN, MONTHLY_PLAN):
        raise HTTPException(status_code=422, detail=f"plan must be one of {ONE_SHOT_PLAN}/{MONTHLY_PLAN}")
    session = create_checkout_session(c, plan=plan)
    return {"url": session.url, "session_id": session.session_id, "mode": session.mode}


@router.get("/demo/checkout", response_class=HTMLResponse)
def demo_checkout_page(session_id: str, campaign_id: int, plan: str, next: str = "/"):
    """Static HTML page used only in DEMO_MODE to simulate paying — clicking
    the button posts to /webhooks/stripe with a canned event so prospects
    can walk through the full paid-unlock flow without Stripe."""
    return HTMLResponse(f"""
<!doctype html><meta charset="utf-8">
<title>Demo checkout · Lead Revival</title>
<style>
body {{ background:#0b0a08;color:#f2ede2;font-family:Inter,sans-serif;padding:40px;max-width:560px;margin:0 auto; }}
.card {{ background:#15120d;border:1px solid #3a2e1e;border-radius:14px;padding:28px; }}
h1 {{ font-size:22px;margin:0 0 10px; }}
p {{ color:#9c8f78;font-size:14px;line-height:1.5; }}
.btn {{ background:linear-gradient(135deg,#e8793c,#f6a06b);color:#0b0a08;border:none;padding:12px 22px;
       border-radius:8px;font-weight:700;font-size:14px;cursor:pointer;font-family:inherit;margin-top:18px; }}
.tag {{ display:inline-block;background:rgba(232,121,60,.15);color:#f6a06b;padding:3px 10px;
       border-radius:999px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:700; }}
</style>
<div class="card">
  <span class="tag">Demo mode</span>
  <h1>Stripe checkout stub</h1>
  <p>Campaign #{campaign_id} · plan: <b>{plan}</b></p>
  <p>In DEMO_MODE no card is charged. Clicking below fires a Stripe
  <code>checkout.session.completed</code> webhook and flips the campaign to paid.</p>
  <form method="POST" action="/webhooks/stripe"
        onsubmit="setTimeout(()=>location.href='{next}',100)">
    <input type="hidden" name="_demo" value="1">
    <input type="hidden" name="campaign_id" value="{campaign_id}">
    <input type="hidden" name="session_id" value="{session_id}">
    <button class="btn" type="submit">Simulate payment</button>
  </form>
</div>
""")


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    body = await request.body()
    settings = get_settings()

    # DEMO mode: accept form posts from the demo-checkout page.
    if settings.demo_mode:
        try:
            form = await request.form()
            if form.get("_demo") == "1":
                cid = int(form.get("campaign_id") or 0)
                c = mark_campaign_paid(db, cid)
                if c is None:
                    raise HTTPException(status_code=404, detail="campaign not found")
                log.info("demo checkout completed for campaign %s", cid)
                return {"ok": True, "campaign_id": c.id, "paid": True}
        except Exception as e:
            log.info("demo webhook parse fallthrough: %s", e)

    # Real Stripe path — uses stripe.Webhook.construct_event which enforces
    # the 5-minute timestamp tolerance and rejects replays for us.
    event = await verify_stripe_event(request, body)
    if event is None:
        raise HTTPException(status_code=403, detail="invalid stripe signature")

    # construct_event returns a Stripe Event object (dict-like).
    event_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", None)
    if event_type != "checkout.session.completed":
        return {"ok": True, "ignored": event_type}

    data_obj = (event.get("data") if isinstance(event, dict) else getattr(event, "data", {})) or {}
    obj = data_obj.get("object") if isinstance(data_obj, dict) else getattr(data_obj, "object", {})
    metadata = (obj.get("metadata") if isinstance(obj, dict) else getattr(obj, "metadata", {})) or {}
    cid = int(metadata.get("campaign_id") or 0)
    c = mark_campaign_paid(db, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="campaign not found in metadata")
    return {"ok": True, "campaign_id": c.id, "paid": True}
