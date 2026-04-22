# Why this exists: DEMO_MODE path. Generates deterministic per-lead revival
# content without calling Claude, so the whole app can run with no keys.
# The templates are intentionally close to what a well-tuned real Claude
# output would look like — so DEMO_MODE previews look realistic to a
# prospect, not placeholder-ish.
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class LeadContext:
    name: str
    vertical: str
    source: Optional[str]
    last_contact: Optional[date]
    notes: Optional[str]
    age_days: Optional[int]
    avg_ticket: float


# Per-vertical hook libraries. Day-10 uses the seasonal hook; earlier days
# keep it generic so they survive any time of year.
VERTICAL_COPY = {
    "septic": {
        "reopen": "just clearing out my inbox from earlier this year and saw your note about septic service",
        "day3":   "circling back on the septic quote — still happy to walk a tank and email a number",
        "day10":  "heading into the summer rush — easier to book a pump before July than in the middle of it",
        "day24":  "last ping from me — if the timing isn't right, no worries. If it ever is, you've got my number",
        "ask":    "Want me to send the quick quote or swing by next week?",
    },
    "roofing": {
        "reopen": "following up on the roof you had me look at earlier this year",
        "day3":   "wanted to check in on the roof — no pressure, just keeping the line open",
        "day10":  "storm season windows are tight — if you want me out before the weather turns, good time to grab a slot",
        "day24":  "last check-in. If you went with someone else, that's totally fine — otherwise I'm here",
        "ask":    "Reply YES and I'll send a slot for a free inspection this week.",
    },
    "hvac": {
        "reopen": "saw your note about the AC / heating system and wanted to reconnect",
        "day3":   "nudging on the HVAC estimate — happy to re-scope if anything's changed",
        "day10":  "we're booking tune-ups before the season flips — cheaper now than an emergency call later",
        "day24":  "last message from me. If you're sorted, glad to hear. If you want a hand, reply back",
        "ask":    "Want me to get a tech out this week for a diagnostic?",
    },
    "plumbing": {
        "reopen": "circling back on the plumbing job you reached out about",
        "day3":   "quick bump — still happy to send a fixed quote when you're ready",
        "day10":  "winter pipe-freeze season coming — want to get ahead of it before it's an emergency",
        "day24":  "final ping. If the timing never lines up, no hard feelings",
        "ask":    "Reply YES and I'll send a time that works.",
    },
    "electrical": {
        "reopen": "reaching out on the electrical work you asked about a while back",
        "day3":   "checking in — permits and pricing are still good from last time",
        "day10":  "panel/EV charger slots fill up early — pick a week now and we'll lock it",
        "day24":  "last note from me. If the project's off, totally fine — otherwise reply back",
        "ask":    "Reply YES to lock a slot this month.",
    },
}

# Tone modifier based on lead age — older leads get warmer/softer openings.
def _age_modifier(age_days: Optional[int]) -> str:
    if age_days is None:
        return ""
    if age_days < 60:
        return "Hey"
    if age_days < 180:
        return "Hi"
    if age_days < 365:
        return "Hi"
    return "Hey — long time"


def _first_name(full: str) -> str:
    return (full or "there").strip().split()[0]


def _urgency_score(ctx: LeadContext) -> int:
    """Deterministic-but-varied urgency 3-9 based on vertical + source + age.

    Scoring rubric (defensible — will match the real pipeline's instincts):
    - Base by vertical volatility: HVAC 7, roofing 6, plumbing 6, septic 5, electrical 4
    - +2 if source is a high-intent channel (referral, phone inquiry)
    - -1 if age > 1 year, -2 if > 2 years
    - +1 if there's a notes field (someone took time to describe it)
    """
    base = {"hvac": 7, "roofing": 6, "plumbing": 6, "septic": 5, "electrical": 4}.get(ctx.vertical, 5)
    src = (ctx.source or "").lower()
    if any(k in src for k in ("referral", "phone", "word of mouth")):
        base += 2
    if ctx.age_days is not None:
        if ctx.age_days > 730:
            base -= 2
        elif ctx.age_days > 365:
            base -= 1
    if ctx.notes and len(ctx.notes.strip()) > 20:
        base += 1
    return max(3, min(9, base))


def _best_time(ctx: LeadContext) -> str:
    # Blue-collar owners answer their phones mid-morning; HVAC emergencies
    # spike afternoon; plumbing/electrical evenings. Deterministic hash to
    # distribute within a vertical.
    vertical_bias = {
        "septic": ("morning", "midday"),
        "roofing": ("morning", "afternoon"),
        "hvac": ("afternoon", "evening"),
        "plumbing": ("evening", "afternoon"),
        "electrical": ("evening", "midday"),
    }.get(ctx.vertical, ("midday", "afternoon"))
    h = int(hashlib.md5(ctx.name.encode("utf-8")).hexdigest(), 16)
    return vertical_bias[h % 2]


def generate_revival(ctx: LeadContext) -> dict:
    copy = VERTICAL_COPY.get(ctx.vertical, VERTICAL_COPY["septic"])
    name = _first_name(ctx.name)
    greeting = _age_modifier(ctx.age_days)

    initial = f"{greeting} {name} — {copy['reopen']}. {copy['ask']} Reply STOP to opt out."
    drip = [
        f"Hey {name}, {copy['day3']}. {copy['ask']}",
        f"Hi {name} — {copy['day10']}. {copy['ask']}",
        f"{name}, {copy['day24']} —",
    ]

    return {
        "initial_msg": initial.strip(),
        "drip_msgs": [m.strip() for m in drip],
        "urgency_score": _urgency_score(ctx),
        "best_time_of_day": _best_time(ctx),
        "strategy_note": (
            f"Warm reconnect for a {ctx.vertical} lead from {ctx.source or 'unknown source'}; "
            f"{ctx.age_days or 'unknown'}d old — play the long game, no push."
        ),
    }
