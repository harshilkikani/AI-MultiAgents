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


# Per-vertical hook libraries — multiple variants per step so no two leads
# in the same vertical get the identical message. Selection is hash-stable
# on lead name so re-seeds produce the same output (reproducible demos).
VERTICAL_VARIANTS = {
    "septic": {
        "reopen": [
            "just clearing out my inbox and saw your note about septic service",
            "circling back — you reached out earlier about septic and I don't want it to fall through",
            "cleaning up old follow-ups today and your septic request was near the top of the pile",
            "saw your septic inquiry from a while back and wanted to check if you're still looking",
            "going through leads I never finished — your septic job was one of them",
        ],
        "day3": [
            "following up on the septic quote — still happy to walk the tank and get you a real number",
            "just bumping this up — any questions on the septic job before I hold a slot?",
            "checking back on the septic — no pressure, just want to keep the door open",
            "nudge on the septic — pricing's the same, happy to come by when it works for you",
        ],
        "day10": [
            "summer rush is coming — pumping before July is way easier than during",
            "heads up — our truck calendar starts filling fast this time of year",
            "wanted to flag this before we lose weekday slots to the summer backlog",
            "if tanks matter on your timeline, this is the last easy booking window",
        ],
        "day24": [
            "last note from me on this one — if the timing's never right, no worries at all",
            "closing the loop on the septic thread. If you ever want us, you've got my number",
            "final ping — won't keep buzzing you. Call when you're ready",
            "alright, stepping off this one. Hope we get the call when it matters",
        ],
        "ask": [
            "Want me to send a quote or swing by next week?",
            "Reply YES and I'll pencil in a visit.",
            "Text back a good day and I'll hold the slot.",
            "Reply YES and I'll send the quick quote today.",
        ],
    },
    "roofing": {
        "reopen": [
            "following up on the roof you had me take a look at",
            "noticed your inspection request never got scheduled — wanted to fix that",
            "circling back on the roof work — didn't want this one to slip",
            "going through old requests and yours was one I didn't close the loop on",
            "checking in on the roof — inspection's still free whenever you're ready",
        ],
        "day3": [
            "wanted to nudge on the roof — happy to send drone photos if that helps you decide",
            "quick bump on the inspection — no pressure, just keeping the line open",
            "checking in on the roof quote — anything I can answer to make it easier?",
            "still happy to get out there for a free inspection when you're ready",
        ],
        "day10": [
            "storm season windows are tight — if you want us out before the weather turns, this is the moment",
            "insurance claim deadlines move fast — want to get an inspection on the books just in case?",
            "seeing more hail activity this week — good time to document the roof before spring ends",
            "crew calendar books out 3 weeks at a time — want to grab a slot while they're open?",
        ],
        "day24": [
            "last check-in. If you went with someone else, that's fine — otherwise I'm here",
            "final note on this one. Inspection offer stands if you ever need it",
            "closing this thread — call me direct if anything changes",
            "won't keep pinging. If the roof holds up, great. If not, you know where to find me",
        ],
        "ask": [
            "Reply YES and I'll send a slot for a free inspection this week.",
            "Text back and I'll have Tom out Thursday or Friday.",
            "Reply YES, I'll book the inspection and send drone pics after.",
            "Want me to pencil in Saturday morning?",
        ],
    },
    "hvac": {
        "reopen": [
            "saw your note about the AC / heat system and wanted to reconnect",
            "circling back on the HVAC work — didn't want this to fall off",
            "going through old estimates — yours was one I never closed on",
            "wanted to check in on the HVAC — still happy to re-quote if anything changed",
            "realized I never followed up on your HVAC inquiry — fixing that now",
        ],
        "day3": [
            "nudging on the HVAC estimate — anything I can answer to get this moving?",
            "quick check-in — happy to send the quote or come re-measure if helpful",
            "still here on the HVAC — pricing's the same, just need a green light",
            "wanted to bump this — any questions before I hold a crew slot?",
        ],
        "day10": [
            "pre-season tune-ups are half an emergency call — good time to lock one in",
            "we're booking tune-ups before the season flips, cheaper now than later",
            "maintenance plan slots are going fast — want the details on how it works?",
            "heads up — our tech calendar tightens when weather turns; easier to grab a slot now",
        ],
        "day24": [
            "last message from me. If you're sorted, glad to hear. If not, reply back",
            "final ping on this one — won't keep buzzing. Call when it matters",
            "closing the loop. Always here if the system acts up",
            "stepping off this one — hope the system's treating you right",
        ],
        "ask": [
            "Want me to get a tech out this week for a diagnostic?",
            "Reply YES, I'll pencil in a tune-up.",
            "Text back a good day and we'll roll a truck.",
            "Reply YES and I'll text you a booking link.",
        ],
    },
    "plumbing": {
        "reopen": [
            "circling back on the plumbing job you asked about",
            "saw your note from a while back — wanted to reconnect on the plumbing work",
            "cleaning up old follow-ups — your plumbing request was near the top",
            "checking in on the plumbing — still happy to send a fixed quote",
            "realized I never closed on your plumbing inquiry — fixing that",
        ],
        "day3": [
            "quick bump — still happy to send a flat-rate quote when you're ready",
            "nudge on the plumbing — any new questions I can handle?",
            "following up — pricing's unchanged, just need a time that works",
            "checking in — want me to come scope it or just send a number first?",
        ],
        "day10": [
            "winter pipe-freeze season is near — want to get ahead of it before it's an emergency?",
            "water heater season starts now — easier to plan the swap than react to a leak",
            "we're booking rough-ins before the builder rush — grab a slot?",
            "seeing more slab-leak calls this week — good time to get the line camera out if that's a concern",
        ],
        "day24": [
            "final ping. If the timing never lines up, no hard feelings",
            "closing this one out. Call me direct when it matters",
            "last note — hope everything's holding up. We're here if it isn't",
            "stepping off this thread. Don't be a stranger",
        ],
        "ask": [
            "Reply YES and I'll send a time that works.",
            "Text back a day and I'll have the crew out.",
            "Reply YES, I'll send a rough number first.",
            "Want me to roll a truck tomorrow morning?",
        ],
    },
    "electrical": {
        "reopen": [
            "reaching out on the electrical work you asked about",
            "circling back on the panel / wiring request — didn't want this to slip",
            "cleaning up old requests — yours was one I never finished",
            "saw your electrical inquiry from a while back — still happy to help",
            "going through lost threads — your electrical job was one",
        ],
        "day3": [
            "checking in — permits and pricing are still good from last time",
            "quick bump — any questions on the electrical job before I lock a slot?",
            "following up on the wire run — happy to re-scope if needed",
            "nudge on the electrical — we can get you on the calendar whenever",
        ],
        "day10": [
            "panel / EV charger slots fill up early — pick a week now and we'll lock it",
            "utility rebate deadlines creep up fast — want to lock in pricing while they're active?",
            "year-end tax credit windows are closing — want the rebate paperwork started?",
            "our wire prices go up next month when the supply contract renews — good time to commit",
        ],
        "day24": [
            "last note from me. If the project's off, totally fine — otherwise reply back",
            "final ping — closing this thread out. Always here",
            "stepping off this one — licensed and insured whenever you need us",
            "won't keep pinging. Panel upgrades aren't going anywhere; we'll be here",
        ],
        "ask": [
            "Reply YES to lock a slot this month.",
            "Text back a good day and I'll send the scope + price.",
            "Reply YES, I'll handle the permit.",
            "Want me to swing by and confirm the scope in person?",
        ],
    },
}

# Source-aware opener fragments — referenced when we know where the lead
# came from. Keeps the thread grounded ("you filled out my Facebook form
# in October") instead of floating.
SOURCE_FLAVOR = {
    "facebook": "from your Facebook inquiry",
    "google":   "from your Google search that came through",
    "phone":    "from the call you left",
    "referral": "from the referral",
    "website":  "from the form on our site",
    "yelp":     "from Yelp",
    "jobber":   "",  # Jobber is our own CRM — don't echo
}


def _pick(options, seed_key: str, bucket: str) -> str:
    """Deterministic pick from a list: stable across runs, varied across leads."""
    h = int(hashlib.md5(f"{seed_key}|{bucket}".encode("utf-8")).hexdigest(), 16)
    return options[h % len(options)]


def _source_tag(source: Optional[str]) -> str:
    if not source:
        return ""
    s = source.lower()
    for key, flavor in SOURCE_FLAVOR.items():
        if key in s:
            return flavor
    return ""


def _age_greeting(age_days: Optional[int], name: str) -> str:
    """Opener varies by age — fresher leads get direct, older get softer."""
    if age_days is None:
        return f"Hey {name}"
    if age_days < 60:
        return f"Hey {name}"
    if age_days < 180:
        return f"Hi {name}"
    if age_days < 365:
        return f"Hey {name}, been a minute"
    return f"{name} — long time"


def _first_name(full: str) -> str:
    return (full or "there").strip().split()[0]


def _urgency_score(ctx: LeadContext) -> int:
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
    vertical_bias = {
        "septic": ("morning", "midday"),
        "roofing": ("morning", "afternoon"),
        "hvac": ("afternoon", "evening"),
        "plumbing": ("evening", "afternoon"),
        "electrical": ("evening", "midday"),
    }.get(ctx.vertical, ("midday", "afternoon"))
    h = int(hashlib.md5(ctx.name.encode("utf-8")).hexdigest(), 16)
    return vertical_bias[h % 2]


def _notes_callback(notes: Optional[str]) -> str:
    """If the lead's notes mention a specific detail, reference it lightly.
    Keeps the message grounded in their context instead of generic."""
    if not notes or len(notes.strip()) < 15:
        return ""
    n = notes.lower()
    if "emergency" in n or "urgent" in n:
        return " — know it was urgent back then, hope you got it handled"
    if "quote" in n:
        return " — happy to resend the quote if you want"
    if "install" in n:
        return " — the install scope is still easy on our end"
    if "pump" in n:
        return " — the pump job is still a same-week booking for us"
    if "leak" in n:
        return " — hoping the leak's not worse now"
    return ""


def generate_revival(ctx: LeadContext) -> dict:
    variants = VERTICAL_VARIANTS.get(ctx.vertical, VERTICAL_VARIANTS["septic"])
    name = _first_name(ctx.name)
    seed = ctx.name  # stable per lead

    # Pick one variant per bucket — hash-stable but different per lead.
    reopen = _pick(variants["reopen"], seed, "reopen")
    day3   = _pick(variants["day3"],   seed, "day3")
    day10  = _pick(variants["day10"],  seed, "day10")
    day24  = _pick(variants["day24"],  seed, "day24")
    ask    = _pick(variants["ask"],    seed, "ask")
    ask_b  = _pick(variants["ask"],    seed, "ask_alt")  # second ask variant for Day-3 so it reads different from Day-0

    greeting_open = _age_greeting(ctx.age_days, name)
    src = _source_tag(ctx.source)
    notes_hint = _notes_callback(ctx.notes)
    src_block = f" {src}" if src else ""

    # Day-0: varied structure. 50% "Greeting — context. Ask." / 50% "Greeting. Context. Ask." so
    # the thread doesn't feel autopopulated.
    h = int(hashlib.md5(f"{seed}|shape".encode()).hexdigest(), 16) % 3
    if h == 0:
        initial = f"{greeting_open} — {reopen}{src_block}{notes_hint}. {ask} Reply STOP to opt out."
    elif h == 1:
        initial = f"{greeting_open}, {reopen}{src_block}{notes_hint}. {ask} Reply STOP to opt out."
    else:
        initial = f"{greeting_open} — quick one: {reopen}{src_block}{notes_hint}. {ask} Reply STOP to opt out."

    # Day-3: shorter, direct bump. Skip the src/notes callbacks — they already saw it on Day-0.
    drip_day3 = f"{name}, {day3}. {ask_b}"

    # Day-10: seasonal. Strong hook, no name repeat if feels pushy.
    shape10 = int(hashlib.md5(f"{seed}|s10".encode()).hexdigest(), 16) % 2
    drip_day10 = f"{name} — {day10}. {ask}" if shape10 == 0 else f"Quick heads-up, {name}: {day10}. {ask}"

    # Day-24: graceful close. Name stays in every message so tests + thread
    # readability both hold.
    shape24 = int(hashlib.md5(f"{seed}|s24".encode()).hexdigest(), 16) % 2
    drip_day24 = f"{name}, {day24} —" if shape24 == 0 else f"{name} — {day24}. If you ever do need us, just text back."

    return {
        "initial_msg": initial.strip(),
        "drip_msgs": [
            drip_day3.strip(),
            drip_day10.strip(),
            drip_day24.strip(),
        ],
        "urgency_score": _urgency_score(ctx),
        "best_time_of_day": _best_time(ctx),
        "strategy_note": (
            f"Warm reconnect for a {ctx.vertical} lead from {ctx.source or 'unknown source'}; "
            f"{ctx.age_days or 'unknown'}d old — play the long game, no push."
        ),
    }
