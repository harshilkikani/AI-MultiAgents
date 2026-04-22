# Why this exists: single entrypoint for "take a lead row, produce 4
# scheduled messages." DEMO_MODE routes through deterministic templates;
# real mode calls Claude once per lead with prompt caching on the system
# block.
#
# The 6-agent pipeline from the parent repo is designed for live inbound
# decisioning (one inbound lead → qualify + route). Revival is bulk per-lead
# message generation. One Claude call per lead with a well-structured system
# prompt is both cheaper and produces better message coherence than chaining
# six thin agents. We keep the prompt file in app/prompts/ so it's tunable
# as config, matching the parent repo's pattern.
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.orm import Campaign, Lead, Message
from app.services.revival_templates import LeadContext, generate_revival
from app.utils.logger import get_logger
from app.utils.parser import extract_json
from app.utils.settings import get_settings

log = get_logger("revival")
_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class RevivalOutput(BaseModel):
    initial_msg: str = Field(min_length=1, max_length=400)
    drip_msgs: list[str] = Field(min_length=3, max_length=3)
    urgency_score: int = Field(ge=1, le=10)
    best_time_of_day: str
    strategy_note: str = ""


DRIP_OFFSETS_DAYS = (0, 3, 10, 24)  # day-0 (initial), day-3, day-10, day-24


def _load_prompt() -> str:
    return (_PROMPTS_DIR / "revival_system.txt").read_text(encoding="utf-8")


def _build_context(lead: Lead, avg_ticket: float) -> LeadContext:
    today = date.today()
    age_days = (today - lead.last_contact).days if lead.last_contact else None
    return LeadContext(
        name=lead.name,
        vertical=lead.campaign.vertical if lead.campaign else "septic",
        source=lead.source,
        last_contact=lead.last_contact,
        notes=lead.notes,
        age_days=age_days,
        avg_ticket=avg_ticket,
    )


def _claude_generate(ctx: LeadContext) -> dict:
    """Real path: one Claude call per lead. Kept tight to land under the
    300-token budget from the acceptance criteria."""
    from app.utils.llm_client import call_claude  # local import: avoid triggering Anthropic client in DEMO
    system = _load_prompt()
    user = (
        "LEAD CONTEXT:\n"
        f"- name: {ctx.name}\n"
        f"- vertical: {ctx.vertical}\n"
        f"- source: {ctx.source or 'unknown'}\n"
        f"- last_contact: {ctx.last_contact.isoformat() if ctx.last_contact else 'unknown'}\n"
        f"- age_days: {ctx.age_days if ctx.age_days is not None else 'unknown'}\n"
        f"- avg_ticket: ${ctx.avg_ticket:.0f}\n"
        f"- notes: {ctx.notes or ''}\n"
        "\nReturn the JSON object only."
    )
    raw = call_claude(system, user, max_tokens=600, use_cache=True)
    try:
        data = extract_json(raw)
        validated = RevivalOutput.model_validate(data)
        return validated.model_dump()
    except (ValueError, ValidationError) as e:
        log.warning("revival generate failed; falling back to templates: %s", e)
        return generate_revival(ctx)


def _generate_one(lead: Lead, avg_ticket: float) -> dict:
    ctx = _build_context(lead, avg_ticket=avg_ticket)
    if get_settings().demo_mode:
        return generate_revival(ctx)
    return _claude_generate(ctx)


def _schedule_for(base: datetime, day_offset: int) -> datetime:
    return base + timedelta(days=day_offset)


def generate_for_campaign(db: Session, campaign_id: int, workspace_id: int) -> dict:
    """Generate 4 messages per lead in the campaign. Idempotent — wipes any
    previously-generated pending messages on re-run so tuning the campaign
    doesn't leave stale text.

    Returns a summary dict for the route to render.
    """
    c = db.get(Campaign, campaign_id)
    if not c or c.workspace_id != workspace_id:
        raise ValueError("campaign not found")

    leads = [l for l in c.leads if l.workspace_id == workspace_id and l.state == "queued"]
    if not leads:
        return {"campaign_id": campaign_id, "leads": 0, "messages": 0, "skipped": 0}

    # Clear prior generated-but-unsent messages (keep any that already sent).
    db.execute(
        delete(Message).where(
            Message.campaign_id == c.id,
            Message.status == "pending",
        )
    )
    db.commit()

    base_time = c.launched_at or datetime.now(UTC).replace(tzinfo=None)
    created = 0
    skipped = 0
    for lead in leads:
        try:
            out = _generate_one(lead, avg_ticket=c.avg_ticket)
        except Exception as e:
            log.error("generate failed for lead %s: %s", lead.id, e)
            skipped += 1
            continue
        msgs = [out["initial_msg"]] + list(out["drip_msgs"])
        for step, (body, day) in enumerate(zip(msgs, DRIP_OFFSETS_DAYS)):
            db.add(Message(
                workspace_id=workspace_id,
                lead_id=lead.id,
                campaign_id=c.id,
                step=step,
                body=body,
                direction="out",
                scheduled_for=_schedule_for(base_time, day),
                status="pending",
            ))
            created += 1
        # Stash per-lead metadata in notes (simplest, no schema change yet).
        if not lead.notes or "urgency=" not in lead.notes:
            meta = f"urgency={out['urgency_score']} best_time={out['best_time_of_day']}"
            lead.notes = (lead.notes + " | " + meta) if lead.notes else meta

    db.commit()
    return {
        "campaign_id": campaign_id,
        "leads": len(leads),
        "messages": created,
        "skipped": skipped,
    }
