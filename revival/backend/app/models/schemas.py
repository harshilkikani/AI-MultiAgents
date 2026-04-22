# Why this exists: Pydantic request/response schemas — keep ORM out of the
# API boundary.
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

VERTICALS = ("septic", "roofing", "hvac", "plumbing", "electrical")


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    vertical: str
    avg_ticket: float = 680.0
    calendly_url: Optional[str] = None
    tone_notes: Optional[str] = None


class CampaignUpdate(BaseModel):
    """Fields the owner can edit. All optional — only provided fields change."""
    name: Optional[str] = None
    avg_ticket: Optional[float] = None
    calendly_url: Optional[str] = None
    tone_notes: Optional[str] = None


class CampaignOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    vertical: str
    avg_ticket: float
    calendly_url: Optional[str]
    tone_notes: Optional[str] = None
    created_at: datetime
    launched_at: Optional[datetime]
    paid: bool
    trial_leads_used: int
    paused: bool = False
    paused_at: Optional[datetime] = None
    lead_count: int = 0

    class Config:
        from_attributes = True


class LeadOut(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    email: Optional[str]
    source: Optional[str]
    last_contact: Optional[date]
    notes: Optional[str]
    state: str

    class Config:
        from_attributes = True


class UploadResult(BaseModel):
    campaign_id: int
    inserted: int
    skipped: int
    skipped_reasons: list[str]
    preview: list[LeadOut]  # first 5 for UI
