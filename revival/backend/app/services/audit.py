# Why this exists: one-stop helper for writing audit events. Every path
# that mutates owner-visible state funnels through `record()`. Keeping the
# plumbing here means tests can snapshot the audit log easily AND a future
# Sentry breadcrumb / Datadog event export ships from one place.
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.orm import AuditEvent


def record(
    db: Session,
    *,
    workspace_id: int,
    event_type: str,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
    summary: Optional[str] = None,
    campaign_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    meta: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    """Add an audit event. Caller owns the commit — we don't commit here
    so multi-step transactions (e.g., pause campaign + write audit) land
    atomically."""
    ev = AuditEvent(
        workspace_id=workspace_id,
        campaign_id=campaign_id,
        lead_id=lead_id,
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        summary=summary,
        before=before,
        after=after,
        meta=meta,
    )
    db.add(ev)
    return ev
