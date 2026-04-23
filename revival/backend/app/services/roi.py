# Why this exists: one place to compute campaign stats + ROI so the list
# page, detail page, and printable report all agree to the penny.
from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.orm import Campaign, Lead, Message

# Pricing model — kept here so a future tier change is one edit.
ONE_SHOT_CAMPAIGN_FEE_USD = 1500

# What fraction of "replied_hot but not booked" leads we count as pipeline
# (vs. recovered). Defensible middle ground for sales-call math.
PIPELINE_CONVERSION_FACTOR = 0.5


@dataclass
class CampaignStats:
    campaign_id: int
    state_counts: dict[str, int]
    total_leads: int
    messages_sent: int
    messages_pending: int
    messages_cancelled: int
    messages_failed: int
    inbound_count: int

    booked_count: int
    hot_count: int
    avg_ticket: float

    est_recovered_revenue: float
    est_pipeline_revenue: float
    keres_cost: float
    net: float


_STATES = ("queued", "contacted", "replied_hot", "replied_no", "booked", "dead", "opted_out")


def compute_stats(db: Session, campaign: Campaign) -> CampaignStats:
    # State histogram
    rows = db.execute(
        select(Lead.state, func.count(Lead.id))
        .where(Lead.campaign_id == campaign.id)
        .group_by(Lead.state)
    ).all()
    state_counts = {s: 0 for s in _STATES}
    for state, n in rows:
        state_counts[state] = int(n)

    total_leads = sum(state_counts.values())
    booked = state_counts["booked"]
    hot = state_counts["replied_hot"]

    # Message histogram
    sent = int(db.scalar(select(func.count(Message.id)).where(
        Message.campaign_id == campaign.id, Message.status == "sent", Message.direction == "out",
    )) or 0)
    pending = int(db.scalar(select(func.count(Message.id)).where(
        Message.campaign_id == campaign.id, Message.status == "pending",
    )) or 0)
    cancelled = int(db.scalar(select(func.count(Message.id)).where(
        Message.campaign_id == campaign.id, Message.status == "cancelled",
    )) or 0)
    failed = int(db.scalar(select(func.count(Message.id)).where(
        Message.campaign_id == campaign.id, Message.status == "failed",
    )) or 0)
    inbound = int(db.scalar(select(func.count(Message.id)).where(
        Message.campaign_id == campaign.id, Message.direction == "in",
    )) or 0)

    avg_ticket = float(campaign.avg_ticket or 0.0)
    est_recovered = booked * avg_ticket
    est_pipeline = (booked * avg_ticket) + (hot * avg_ticket * PIPELINE_CONVERSION_FACTOR)
    keres_cost = float(ONE_SHOT_CAMPAIGN_FEE_USD)
    net = est_recovered - keres_cost

    return CampaignStats(
        campaign_id=campaign.id,
        state_counts=state_counts,
        total_leads=total_leads,
        messages_sent=sent,
        messages_pending=pending,
        messages_cancelled=cancelled,
        messages_failed=failed,
        inbound_count=inbound,
        booked_count=booked,
        hot_count=hot,
        avg_ticket=avg_ticket,
        est_recovered_revenue=est_recovered,
        est_pipeline_revenue=est_pipeline,
        keres_cost=keres_cost,
        net=net,
    )


def stats_as_dict(s: CampaignStats) -> dict:
    return asdict(s)
