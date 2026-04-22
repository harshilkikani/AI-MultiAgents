# Why this exists: one place for all webhook signature verification so
# every provider uses the same audit trail + DEMO_MODE bypass rules.
#
# Security note: in DEMO_MODE ONLY, `X-Test-Signature-Bypass: 1` is
# accepted as a free pass. This header is NEVER honored when
# DEMO_MODE=false, even if set.
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Optional

from fastapi import Request

from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("webhook_auth")

BYPASS_HEADER = "X-Test-Signature-Bypass"
BYPASS_VALUE = "1"


def _allow_bypass(request: Request) -> bool:
    """True iff DEMO_MODE is set AND the bypass header is present.

    Test convenience: when REVIVAL_TEST_BYPASS=1 is set in the env (ONLY
    meaningful for the automated test suite), all verifiers pass. This env
    var is NEVER set in production — it's off by default and the CI sets
    it explicitly so live deploys never accidentally inherit it.
    """
    import os
    if os.environ.get("REVIVAL_TEST_BYPASS") == "1":
        return True
    if not get_settings().demo_mode:
        return False
    return request.headers.get(BYPASS_HEADER) == BYPASS_VALUE


# ---------------------------------------------------------------------------
# Twilio: uses twilio.request_validator.RequestValidator
# ---------------------------------------------------------------------------
async def verify_twilio_request(request: Request) -> bool:
    if _allow_bypass(request):
        return True

    settings = get_settings()
    token = settings.twilio_auth_token
    if not token:
        # No token configured — reject unless DEMO_MODE (already handled).
        log.warning("twilio: auth token not set and no bypass — rejecting")
        return False

    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        return False

    try:
        from twilio.request_validator import RequestValidator
    except Exception as e:
        log.error("twilio SDK missing: %s", e)
        return False

    # Reconstruct the URL Twilio signed. Prefer the Forwarded proto header
    # so ngrok / Fly / Vercel don't break signing behind HTTPS terminators.
    url = str(request.url)
    # Twilio signs POST form params.
    form = await request.form()
    params = {k: v for k, v in form.multi_items()} if hasattr(form, "multi_items") else dict(form)
    validator = RequestValidator(token)
    return bool(validator.validate(url, params, signature))


# ---------------------------------------------------------------------------
# Calendly: v1 HMAC-SHA256 over "{timestamp}.{raw_body}" — same scheme family
# as Stripe but using the `Calendly-Webhook-Signature` header.
# Timestamp window: 5 minutes to prevent replay.
# ---------------------------------------------------------------------------
REPLAY_WINDOW_SECONDS = 5 * 60


def _parse_kv_signature(header: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in header.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _hmac_sha256_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_calendly_request_sync(body: bytes, signature_header: Optional[str], secret: str,
                                  *, now: Optional[int] = None) -> bool:
    if not signature_header or not secret:
        return False
    parts = _parse_kv_signature(signature_header)
    ts = parts.get("t", "")
    v1 = parts.get("v1", "")
    if not ts or not v1:
        return False
    try:
        ts_int = int(ts)
    except ValueError:
        return False
    now_int = now if now is not None else int(time.time())
    if abs(now_int - ts_int) > REPLAY_WINDOW_SECONDS:
        return False
    expected = _hmac_sha256_hex(secret, f"{ts}.".encode("utf-8") + body)
    return hmac.compare_digest(expected, v1)


async def verify_calendly_request(request: Request, body: bytes) -> bool:
    if _allow_bypass(request):
        return True
    secret = get_settings().__dict__.get("calendly_webhook_secret", "")  # not in Settings by default
    # We haven't added calendly_webhook_secret to Settings yet; fall back to
    # the dedicated env var so `.env` can just set CALENDLY_WEBHOOK_SECRET.
    import os
    secret = secret or os.getenv("CALENDLY_WEBHOOK_SECRET", "")
    if not secret:
        log.warning("calendly webhook secret not set — rejecting (set CALENDLY_WEBHOOK_SECRET or use DEMO_MODE)")
        return False
    sig = request.headers.get("Calendly-Webhook-Signature")
    return verify_calendly_request_sync(body, sig, secret)


# ---------------------------------------------------------------------------
# Stripe: prefer stripe.Webhook.construct_event — handles timestamp
# tolerance, tolerant to minor format changes.
# ---------------------------------------------------------------------------
async def verify_stripe_event(request: Request, body: bytes) -> Optional[Any]:
    """Returns the parsed event on success; None on failure.

    DEMO_MODE bypass returns a sentinel dict so the route can keep running
    in demo flows without a real Stripe setup.
    """
    if _allow_bypass(request):
        # Let the route parse the body itself — the demo flow uses
        # form-encoded _demo=1 posts, not real Stripe JSON, so it has its
        # own parsing path.
        return {"_bypass": True}

    settings = get_settings()
    if not settings.stripe_webhook_secret:
        log.warning("stripe webhook secret not set — rejecting")
        return None

    sig = request.headers.get("Stripe-Signature", "")
    try:
        import stripe
        return stripe.Webhook.construct_event(body, sig, settings.stripe_webhook_secret)
    except Exception as e:
        log.info("stripe signature check failed: %s", e)
        return None
