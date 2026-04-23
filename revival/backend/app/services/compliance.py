# Why this exists: all TCPA checks live in one place so routes, scheduler,
# and manual-send share the same rules. Every send path MUST call
# can_send() before hitting Twilio — no exceptions.
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.orm import ComplianceEvent, Message, OptOut
from app.utils.logger import get_logger

log = get_logger("compliance")

# --- Configurable limits (defensible + conservative) --------------------
FREQUENCY_WINDOW = timedelta(days=30)
FREQUENCY_CAP = 5            # max outbound SMS per phone per workspace per 30d
DNC_CACHE_TTL = timedelta(hours=24)

# Local deny-list — swap for a real DNC API call (costs $$; requires SAN
# registration) when the first real pilot goes live. Keeping the interface
# here means that's a one-function swap.
_DNC_FILE = Path(__file__).resolve().parents[2] / "data" / "dnc_deny.txt"
_dnc_cache: Optional[set[str]] = None


def _load_dnc() -> set[str]:
    """Load DNC deny list from disk. Safe to call every check — cheap."""
    global _dnc_cache
    if _dnc_cache is not None:
        return _dnc_cache
    out: set[str] = set()
    if _DNC_FILE.exists():
        for line in _DNC_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Normalize to digits-only so "+12295550142", "12295550142",
                # "229-555-0142" all match.
                digits = "".join(c for c in line if c.isdigit())
                if digits:
                    out.add(digits)
    _dnc_cache = out
    return out


def invalidate_dnc_cache() -> None:
    global _dnc_cache
    _dnc_cache = None


def _phone_digits(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    d = "".join(c for c in phone if c.isdigit())
    return d or None


@dataclass
class SendDecision:
    allowed: bool
    reason: str  # "ok" | "opted_out" | "dnc_blocked" | "frequency_capped" | "no_phone"
    detail: Optional[str] = None

    def __bool__(self) -> bool:
        return self.allowed


def is_opted_out(db: Session, phone: str, workspace_id: int) -> bool:
    row = db.scalars(
        select(OptOut).where(OptOut.workspace_id == workspace_id, OptOut.phone == phone)
    ).first()
    return row is not None


def is_on_dnc(phone: str) -> bool:
    digits = _phone_digits(phone)
    if not digits:
        return False
    return digits in _load_dnc()


def recent_send_count(db: Session, phone: str, workspace_id: int, now: Optional[datetime] = None) -> int:
    """How many outbound SMS have been SENT to this phone in the last
    FREQUENCY_WINDOW within this workspace?"""
    now = now or datetime.now(UTC).replace(tzinfo=None)
    cutoff = now - FREQUENCY_WINDOW
    return int(db.scalar(
        select(func.count(Message.id)).where(
            Message.workspace_id == workspace_id,
            Message.direction == "out",
            Message.status == "sent",
            Message.sent_at >= cutoff,
        ).join(
            # join to filter by phone via Lead
            Message.lead.has(phone=phone),  # type: ignore[attr-defined]
        )
    ) or 0)


def _recent_send_count_by_join(db: Session, phone: str, workspace_id: int, now: Optional[datetime] = None) -> int:
    """Fallback counter that doesn't rely on the .has() relationship — uses
    an explicit join through Lead table for portability."""
    from app.models.orm import Lead
    now = now or datetime.now(UTC).replace(tzinfo=None)
    cutoff = now - FREQUENCY_WINDOW
    return int(db.scalar(
        select(func.count(Message.id))
        .join(Lead, Lead.id == Message.lead_id)
        .where(
            Message.workspace_id == workspace_id,
            Message.direction == "out",
            Message.status == "sent",
            Message.sent_at >= cutoff,
            Lead.phone == phone,
        )
    ) or 0)


def can_send(db: Session, phone: Optional[str], workspace_id: int, *, now: Optional[datetime] = None) -> SendDecision:
    """Top-level gate: call this BEFORE every outbound SMS.

    Order of checks matters: opt-out first (terminal), DNC next, frequency
    last (might be transient). Returns a SendDecision carrying the reason so
    the caller can log the block to the audit trail.
    """
    if not phone:
        return SendDecision(False, "no_phone", "lead has no phone on file")
    if is_opted_out(db, phone, workspace_id):
        return SendDecision(False, "opted_out", f"{phone} has opted out of workspace {workspace_id}")
    if is_on_dnc(phone):
        return SendDecision(False, "dnc_blocked", f"{phone} is on the DNC deny list")
    count = _recent_send_count_by_join(db, phone, workspace_id, now=now)
    if count >= FREQUENCY_CAP:
        return SendDecision(False, "frequency_capped",
                            f"{phone} has received {count} sends in the last {FREQUENCY_WINDOW.days}d (cap={FREQUENCY_CAP})")
    return SendDecision(True, "ok")


def record_event(
    db: Session,
    *,
    event_type: str,
    workspace_id: int,
    phone: Optional[str] = None,
    lead_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    body: Optional[str] = None,
    message_sid: Optional[str] = None,
    meta: Optional[dict] = None,
) -> ComplianceEvent:
    ev = ComplianceEvent(
        event_type=event_type,
        workspace_id=workspace_id,
        phone=phone,
        lead_id=lead_id,
        campaign_id=campaign_id,
        body=body,
        message_sid=message_sid,
        meta=meta,
    )
    db.add(ev)
    return ev  # caller commits


def opt_out(
    db: Session,
    *,
    phone: str,
    workspace_id: int,
    source: Literal["sms_reply", "manual", "dnc_registry", "webform"],
    proof_body: Optional[str] = None,
    proof_message_sid: Optional[str] = None,
    lead_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
) -> OptOut:
    """Idempotent opt-out. Writes to opt_outs + compliance_events. Safe to
    call more than once — the UNIQUE constraint protects duplicates."""
    existing = db.scalars(
        select(OptOut).where(OptOut.workspace_id == workspace_id, OptOut.phone == phone)
    ).first()
    if existing is not None:
        return existing

    row = OptOut(
        workspace_id=workspace_id, phone=phone, source=source,
        proof_body=proof_body, proof_message_sid=proof_message_sid,
    )
    db.add(row)
    record_event(
        db,
        event_type="opted_out",
        workspace_id=workspace_id,
        phone=phone,
        lead_id=lead_id,
        campaign_id=campaign_id,
        body=proof_body,
        message_sid=proof_message_sid,
        meta={"source": source},
    )
    return row


def should_include_stop_footer(step: int) -> bool:
    """Day-0 already has 'Reply STOP to opt out.' baked into the template.
    Add a shorter STOP reminder on Day-10 (step 2) so the thread keeps the
    opt-out path visible. Day-3 and Day-24 stay clean to save characters."""
    return step == 2
