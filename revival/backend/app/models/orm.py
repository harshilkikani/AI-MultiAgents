# Why this exists: all ORM models for Lead Revival in one place.
# workspace_id is already on every row so M7 can drop in auth without a
# schema migration.
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Billing — trial is workspace-wide (not per campaign). First 10 leads
    # generated against any campaign in this workspace are free.
    trial_leads_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # M16 — owner alert routing. When a lead replies hot or books, we ping
    # the shop owner ASAP on these channels (SMS first, Slack second).
    owner_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    owner_timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class User(Base):
    """Authenticated user. `external_id` carries the Supabase user UUID
    (sub claim); local DEMO users get a synthetic id."""
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("external_id", name="uq_users_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class WorkspaceMember(Base):
    """Membership join: a user belongs to 1+ workspaces with a role. All
    cross-workspace lookups go through this table."""
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_member_user_ws"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), default="owner", nullable=False)  # owner | member
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    vertical: Mapped[str] = mapped_column(String(32), nullable=False)
    avg_ticket: Mapped[float] = mapped_column(Float, default=680.0, nullable=False)
    calendly_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    launched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    paid: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)  # 0/1 for sqlite simplicity
    trial_leads_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # M17 — paused campaigns are skipped by the scheduler and can't send
    # via manual-send either. Owner toggles via POST /pause or /resume.
    paused: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # M19 — free-text tone override. Appended to the user prompt so the
    # owner can say "keep it gruff" or "we're in Austin, don't say y'all,
    # it sounds forced" without touching the base system prompt.
    tone_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    leads: Mapped[list["Lead"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_contact: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # M18 — dedup key for records that came from an external CRM (Jobber,
    # ServiceTitan, HubSpot). The CRM's own id is stored here so re-syncs
    # don't insert the same lead twice.
    external_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)  # "jobber" | ...
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    state: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    campaign: Mapped[Campaign] = relationship(back_populates="leads")
    messages: Mapped[list["Message"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class Message(Base):
    # Populated in M2 (generated by the revival pipeline). Kept here so M1's
    # schema doesn't need a migration.
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)

    step: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=initial, 1/2/3=drip
    body: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), default="out", nullable=False)  # out | in
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)  # pending | sent | failed | received
    twilio_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    lead: Mapped[Lead] = relationship(back_populates="messages")


class OptOut(Base):
    """One row per (workspace, phone). Once listed, that number NEVER
    receives another SMS from any campaign in the workspace."""
    __tablename__ = "opt_outs"
    __table_args__ = (UniqueConstraint("workspace_id", "phone", name="uq_opt_outs_ws_phone"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    opted_out_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # "sms_reply" | "manual" | "dnc_registry" | "webform"
    proof_message_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    proof_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class JobberConnection(Base):
    """One Jobber workspace-level OAuth connection. We store encrypted
    tokens via app-level encryption in prod — for v0 they're stored raw
    under the assumption that DB access itself is already privileged."""
    __tablename__ = "jobber_connections"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_jobber_workspace"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    access_token: Mapped[str] = mapped_column(String(2048), nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scopes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_sync_stats: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # active | disconnected | expired


class OwnerAlert(Base):
    """Audit + dedup record for alerts we fire to a shop owner. Prevents
    spamming the same 'lead X replied hot' alert more than once per 4h."""
    __tablename__ = "owner_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # replied_hot | booked
    channel: Mapped[str] = mapped_column(String(16), nullable=False)                 # sms | slack | email
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    twilio_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sent")  # sent | failed | skipped


class AuditEvent(Base):
    """Generalized audit trail. Every state transition and owner-visible
    action appends here so the activity log on CampaignDetail has a
    single source of truth. Separate from ComplianceEvent (which is
    purpose-built for TCPA paper trail)."""
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user | system | webhook | scheduler | api
    actor_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ComplianceEvent(Base):
    """Immutable audit trail. Every block / opt-out / unlock goes here so
    regulators can read the paper trail."""
    __tablename__ = "compliance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # event_type one of: opted_out | opt_in_restored | dnc_blocked |
    # frequency_capped | send_allowed | manual_add
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
