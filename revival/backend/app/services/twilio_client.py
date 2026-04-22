# Why this exists: outbound SMS + DEMO_MODE no-op. Keeps Twilio-specific
# concerns (auth, error mapping) out of the routes and scheduler.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("twilio")


@dataclass
class SendResult:
    sid: Optional[str]
    status: str  # "sent" | "demo" | "failed"
    error: Optional[str] = None


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    s = get_settings()
    if s.demo_mode:
        return None
    if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number):
        raise RuntimeError(
            "Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "TWILIO_FROM_NUMBER in .env, or set DEMO_MODE=true."
        )
    from twilio.rest import Client  # local import so DEMO doesn't need the lib imported
    _client = Client(s.twilio_account_sid, s.twilio_auth_token)
    return _client


def send_sms(to_e164: str, body: str) -> SendResult:
    """Send one SMS. Returns SendResult; never raises on Twilio errors (we
    surface them as status='failed' so the scheduler can mark + move on)."""
    s = get_settings()
    if s.demo_mode:
        log.info("[DEMO] would send SMS to %s: %s", to_e164, body[:80])
        return SendResult(sid=f"demo-{hash((to_e164, body)) & 0xFFFFFFFF:x}", status="demo")

    try:
        client = _get_client()
        msg = client.messages.create(to=to_e164, from_=s.twilio_from_number, body=body)
        return SendResult(sid=msg.sid, status="sent")
    except Exception as e:
        log.exception("twilio send failed")
        return SendResult(sid=None, status="failed", error=str(e))
