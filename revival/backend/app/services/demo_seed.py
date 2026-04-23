# Why this exists: build a believable, mid-flight demo campaign in one
# shot. Gets called by `scripts/seed_demo.py` AND by the /api/demo/reset
# endpoint so sales demos can refresh on demand.
from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Campaign, Lead, Message, Workspace
from app.services.revival_pipeline import generate_for_campaign
from app.utils.logger import get_logger

log = get_logger("demo_seed")

DEMO_WS_ID = 2
DEMO_WS_NAME = "Hatcher Septic Demo"
DEMO_CAMPAIGN_NAME = "Spring 2026 Revival"
DEMO_CALENDLY = "https://calendly.com/hatcher-septic/30min"
DEMO_VERTICAL = "septic"
DEMO_AVG_TICKET = 680.0

# Seed RNG for deterministic demo state — a prospect always sees the same
# numbers, which makes the ROI report a reliable sales exhibit.
_RNG_SEED = 1337

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample_leads.csv"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def wipe_demo(db: Session) -> None:
    """Delete the demo workspace's campaigns, leads, messages. Keeps the
    workspace row so foreign keys are stable."""
    campaigns = db.scalars(select(Campaign).where(Campaign.workspace_id == DEMO_WS_ID)).all()
    for c in campaigns:
        db.delete(c)  # cascades to leads + messages
    # Reset trial counter so re-seeding is idempotent.
    ws = db.get(Workspace, DEMO_WS_ID)
    if ws:
        ws.trial_leads_used = 0
    db.commit()


def _ensure_workspace(db: Session) -> Workspace:
    ws = db.get(Workspace, DEMO_WS_ID)
    if ws is None:
        ws = Workspace(id=DEMO_WS_ID, name=DEMO_WS_NAME)
        db.add(ws)
        db.commit()
        db.refresh(ws)
    else:
        ws.name = DEMO_WS_NAME
        db.commit()
    return ws


def _load_leads(db: Session, campaign: Campaign) -> int:
    """Insert the 200-row fixture CSV as leads on the demo campaign."""
    if not _FIXTURE.exists():
        raise RuntimeError(f"missing fixture at {_FIXTURE}; run scripts/gen_sample_csv.py")
    from app.services.csv_ingest import parse_csv
    leads, _skipped = parse_csv(_FIXTURE.read_bytes())
    for ld in leads:
        db.add(Lead(
            workspace_id=DEMO_WS_ID,
            campaign_id=campaign.id,
            name=ld.name, phone=ld.phone, email=ld.email, source=ld.source,
            last_contact=ld.last_contact, notes=ld.notes,
        ))
    db.commit()
    return len(leads)


def _apply_realistic_progress(db: Session, campaign: Campaign, rng: random.Random) -> dict:
    """Shape the campaign as if it's been running for 10 days.

    Timing model (what a real shop sees):
      - Day-0 sent 10 days ago; Day-3 sent 7 days ago.
      - Day-10 is pending (~today); Day-24 is still 14 days out.
      - Of replies, about 40% come within 36h of Day-0, 35% between Day-3 and
        Day-7, and 25% between Day-7 and now (after Day-3 has also fired).
        Matches real drip campaign behavior — early texters close fast,
        later texters re-engage when a second reminder lands.
      - Booked rate tuned to produce ~11 booked on the 200-row fixture:
        48% reply × 35% yes × 50% yes→booked = 8.4% booked = ~17. Too high.
        Target: 45% × 34% × 42% = 6.4% ≈ 13. Still high. Tuned to
        40% reply × 34% yes × 40% yes→booked = 5.4% = ~11. ✓

    A "maybe" reply leaves the drip going — Day-10 and Day-24 stay pending
    so the shop's follow-up sequence doesn't stop on an "ask me later".
    """
    leads = db.scalars(select(Lead).where(Lead.campaign_id == campaign.id)).all()
    now = _now()
    sent_at_day0 = now - timedelta(days=10)
    sent_at_day3 = now - timedelta(days=7)

    total = len(leads)
    reply_fraction = 0.40

    stats = {"contacted": 0, "replied_hot": 0, "replied_no": 0, "booked": 0, "opted_out": 0, "inbound_msgs": 0}

    def _pick_reply_time() -> "datetime":
        """Distribute replies across the real elapsed campaign window.
        Early replies most common; some trickle in after Day-3 fires.
        A handful come 'just yesterday' — right before Day-10 would."""
        bucket = rng.choices(
            ["early", "mid", "late"],
            weights=[0.40, 0.35, 0.25],
            k=1,
        )[0]
        if bucket == "early":
            # Within 6-36h of Day-0 send.
            return sent_at_day0 + timedelta(hours=rng.randint(6, 36))
        if bucket == "mid":
            # Between Day-3 send (7 days ago) and 3 days ago.
            return sent_at_day3 + timedelta(hours=rng.randint(2, 96))
        # late: within the last 48h.
        return now - timedelta(hours=rng.randint(4, 48))

    for lead in leads:
        msgs = db.scalars(
            select(Message)
            .where(Message.lead_id == lead.id, Message.direction == "out")
            .order_by(Message.step.asc())
        ).all()
        if len(msgs) < 4:
            continue

        day0, day3, day10, day24 = msgs[:4]

        # Day-0 always sends.
        day0.status = "sent"
        day0.sent_at = sent_at_day0
        day0.twilio_sid = f"SM_demo_{lead.id}_0"
        lead.state = "contacted"
        stats["contacted"] += 1

        replies = rng.random() < reply_fraction
        if not replies:
            # Silent lead — Day-3 also sent, Day-10 pending today, Day-24 future.
            day3.status = "sent"
            day3.sent_at = sent_at_day3
            day3.twilio_sid = f"SM_demo_{lead.id}_1"
            day10.scheduled_for = now + timedelta(hours=rng.randint(2, 18))
            day24.scheduled_for = now + timedelta(days=14, hours=rng.randint(0, 12))
            continue

        # Replied — pick intent + timing.
        intent = rng.choices(
            ["yes", "no", "maybe", "stop"],
            weights=[0.34, 0.28, 0.33, 0.05],  # bumped yes for more booked
            k=1,
        )[0]
        reply_at = _pick_reply_time()

        body_map = {
            "yes": rng.choice([
                "yes please", "sounds good, book it", "let's do it", "yeah I'm in",
                "ok come tomorrow", "send me a time", "yes — can you swing by this week?",
                "yeah, finally getting to this", "yep still need it done",
                "yes, what's your next opening", "go ahead", "book me in",
            ]),
            "no":  rng.choice([
                "no thanks", "not interested", "already hired someone",
                "went with another company", "wrong number", "took care of it",
                "we're good now", "nah, sorted it out",
            ]),
            "maybe": rng.choice([
                "how much does it cost?", "what's the price", "call me later",
                "maybe next month", "thinking about it", "need to check with my wife",
                "busy this week, try me next week", "what's the turnaround",
                "depends on pricing", "can you text me a number range?",
            ]),
            "stop": rng.choice(["STOP", "unsubscribe", "cancel", "remove me"]),
        }
        db.add(Message(
            workspace_id=DEMO_WS_ID, lead_id=lead.id, campaign_id=campaign.id,
            step=-1, body=body_map[intent], direction="in", status="received",
            sent_at=reply_at, twilio_sid=f"SM_demo_in_{lead.id}",
        ))
        stats["inbound_msgs"] += 1

        # Day-3 depends on whether it had already fired by reply_at.
        if reply_at < sent_at_day3:
            day3.status = "cancelled"
        else:
            day3.status = "sent"
            day3.sent_at = sent_at_day3
            day3.twilio_sid = f"SM_demo_{lead.id}_1"

        # Day-10/Day-24 handling depends on the intent.
        # yes / no / stop are terminal → cancel future drip.
        # maybe keeps the drip alive, so Day-10 pending and Day-24 future.
        if intent in ("yes", "no", "stop"):
            day10.status = "cancelled"
            day24.status = "cancelled"
        else:  # maybe
            day10.scheduled_for = now + timedelta(hours=rng.randint(2, 18))
            day24.scheduled_for = now + timedelta(days=14, hours=rng.randint(0, 12))

        if intent == "yes":
            lead.state = "replied_hot"
            stats["replied_hot"] += 1
            # Auto-reply: Calendly link. Sent a realistic 30-90s after inbound.
            auto_body = (
                f"Awesome, {lead.name.split()[0]} — here's my calendar, grab the "
                f"slot that works: {DEMO_CALENDLY}"
            )
            auto_reply_at = reply_at + timedelta(seconds=rng.randint(30, 90))
            db.add(Message(
                workspace_id=DEMO_WS_ID, lead_id=lead.id, campaign_id=campaign.id,
                step=99, body=auto_body, direction="out", status="sent",
                sent_at=auto_reply_at,
                twilio_sid=f"SM_demo_auto_{lead.id}",
            ))
            # ~55% of hot leads book → with our fixed RNG seed this lands at
            # ~11 booked out of 200 on the Hatcher Septic fixture.
            if rng.random() < 0.55:
                lead.state = "booked"
                stats["booked"] += 1
                stats["replied_hot"] -= 1
        elif intent == "no":
            lead.state = "replied_no"
            stats["replied_no"] += 1
        elif intent == "stop":
            lead.state = "opted_out"
            stats["opted_out"] += 1
        # maybe: stays contacted, drip continues

    stats["total"] = total
    db.commit()
    return stats


def build_demo(db: Session) -> dict:
    """Wipe + rebuild the demo workspace. Returns a summary."""
    rng = random.Random(_RNG_SEED)
    _ensure_workspace(db)
    wipe_demo(db)

    # Fresh campaign, already paid (so generate's trial gate doesn't trip).
    campaign = Campaign(
        workspace_id=DEMO_WS_ID,
        name=DEMO_CAMPAIGN_NAME,
        vertical=DEMO_VERTICAL,
        avg_ticket=DEMO_AVG_TICKET,
        calendly_url=DEMO_CALENDLY,
        paid=1,
        launched_at=_now() - timedelta(days=10),
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    leads_loaded = _load_leads(db, campaign)
    db.refresh(campaign)
    generate_result = generate_for_campaign(db, campaign.id, DEMO_WS_ID)

    # Apply realistic campaign progress (some sent, some replied, some booked)
    progress = _apply_realistic_progress(db, campaign, rng)

    return {
        "workspace_id": DEMO_WS_ID,
        "campaign_id": campaign.id,
        "leads_loaded": leads_loaded,
        "messages_generated": generate_result["messages"],
        **progress,
    }
