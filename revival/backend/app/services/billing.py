# Why this exists: Stripe Checkout integration. DEMO_MODE returns a
# stub URL; real mode calls stripe-python. All business logic (trial gate,
# paid-flip on webhook) lives here so routes stay thin.
from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import Campaign, Workspace
from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("billing")

TRIAL_LEADS_LIMIT = 10  # free leads per workspace, across all campaigns

ONE_SHOT_PLAN = "one_shot"      # $1,500 per campaign
MONTHLY_PLAN = "monthly"         # $499 / mo always-on


@dataclass
class CheckoutSession:
    url: str
    session_id: str
    mode: str  # "demo" | "live"


def create_checkout_session(
    campaign: Campaign,
    plan: str,
    *,
    success_url: str = "http://localhost:5174/campaigns/{id}?paid=1",
    cancel_url: str = "http://localhost:5174/campaigns/{id}?paid=0",
) -> CheckoutSession:
    """Create a Checkout Session for a campaign. In DEMO_MODE returns a
    stub URL that points at our own /webhooks/stripe so the demo can
    self-complete a checkout without leaving the host."""
    if plan not in (ONE_SHOT_PLAN, MONTHLY_PLAN):
        raise ValueError(f"unknown plan: {plan}")

    s = get_settings()
    sid = f"cs_{'demo' if s.demo_mode else 'live'}_{campaign.id}_{plan}"
    success = success_url.format(id=campaign.id)

    if s.demo_mode:
        # Demo checkout flows through a helper page that POSTs back to our
        # webhook (see /routes/billing.py). No real Stripe involvement.
        url = f"/demo/checkout?session_id={sid}&campaign_id={campaign.id}&plan={plan}&next={success}"
        return CheckoutSession(url=url, session_id=sid, mode="demo")

    # Real Stripe path.
    price_id = {
        ONE_SHOT_PLAN: s.stripe_price_one_shot,
        MONTHLY_PLAN: s.stripe_price_monthly,
    }[plan]
    if not (s.stripe_secret_key and price_id):
        raise RuntimeError(
            "Stripe not configured. Set STRIPE_SECRET_KEY + STRIPE_PRICE_* "
            "in .env, or set DEMO_MODE=true."
        )
    import stripe
    stripe.api_key = s.stripe_secret_key
    mode = "payment" if plan == ONE_SHOT_PLAN else "subscription"
    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success,
        cancel_url=cancel_url.format(id=campaign.id),
        metadata={"campaign_id": str(campaign.id), "plan": plan},
    )
    return CheckoutSession(url=session.url, session_id=session.id, mode="live")


def workspace_has_remaining_trial(ws: Workspace, lead_count: int) -> bool:
    """Trial allowance covers the next `lead_count` leads IFF the workspace
    still has headroom under TRIAL_LEADS_LIMIT."""
    return (ws.trial_leads_used + lead_count) <= TRIAL_LEADS_LIMIT


def gate_generate(db: Session, campaign: Campaign, workspace: Workspace, lead_count: int) -> Optional[str]:
    """Return None if allowed; otherwise a human-readable block reason."""
    if bool(campaign.paid):
        return None
    if workspace_has_remaining_trial(workspace, lead_count):
        return None
    return (
        f"Campaign not paid and trial exhausted "
        f"({workspace.trial_leads_used}/{TRIAL_LEADS_LIMIT} trial leads used). "
        f"Pay for this campaign to unlock generation."
    )


def mark_campaign_paid(db: Session, campaign_id: int) -> Optional[Campaign]:
    c = db.get(Campaign, campaign_id)
    if c is None:
        return None
    c.paid = 1
    db.commit()
    db.refresh(c)
    return c


def verify_stripe_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """Minimal verifier — in prod use `stripe.Webhook.construct_event`.
    Here we support the same HMAC-SHA256 scheme so tests can sign payloads
    without depending on Stripe's client."""
    if not signature_header or not secret:
        return False
    # Stripe uses a versioned scheme: "t=...,v1=..."
    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    ts = parts.get("t", "")
    v1 = parts.get("v1", "")
    if not ts or not v1:
        return False
    signed = f"{ts}.".encode() + payload_bytes
    import hashlib
    computed = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, v1)
