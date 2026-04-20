"""Deterministic canned responses so the UI is demoable without an API key.

Switch on by setting DEMO_MODE=true in backend/.env.
"""
import json


def demo_response_for(system_prompt: str, user_prompt: str) -> str:
    sp = system_prompt.lower()
    up = user_prompt.lower()

    is_urgent = any(w in up for w in [
        "asap", "drowning", "this week", "yesterday", "peak season",
        "losing leads", "killing us", "speed-to-lead",
        '"urgency": "high"'
    ])
    has_budget = any(w in up for w in ["$", "/mo", "pricing"])
    no_budget = "no budget" in up
    low_intent = any(w in up for w in [
        "just curious", "maybe later", "love the concept",
        "send me some info", "too small", "bored@",
        "poking around", "browsing", "cool concept", "no budget",
        "what exactly does it do", "saw this on a webinar"
    ])

    # For downstream agents (response, followup, action, manager), infer tier
    # from the qualification JSON that was passed in via user_prompt. This is
    # more reliable than keyword-matching across the aggregated payload.
    upstream_tier = None
    if '"tier": "high"' in up:
        upstream_tier = "High"
    elif '"tier": "medium"' in up:
        upstream_tier = "Medium"
    elif '"tier": "low"' in up:
        upstream_tier = "Low"

    # Identify the agent by its unique role header in the system prompt.
    # Order matters — check most specific first.
    if "manager / orchestrator agent" in sp:
        agent = "manager"
    elif "action recommendation agent" in sp:
        agent = "action"
    elif "follow-up strategy agent" in sp:
        agent = "followup"
    elif "response agent" in sp:
        agent = "response"
    elif "qualification agent" in sp:
        agent = "qualification"
    elif "intake agent" in sp:
        agent = "intake"
    else:
        agent = "unknown"

    if agent == "intake":
        # Detect business type from message keywords
        biz_keywords = [
            ("septic", ["septic", "pumping", "drain service"]),
            ("roofing", ["roofing", "roofer", "hail", "shingle"]),
            ("hvac", ["hvac", "air conditioning", "heating", "ac repair"]),
            ("personal injury", ["personal injury", "pi firm"]),
            ("legal", ["law firm", "lawyer", "attorney", "esq"]),
            ("mortgage", ["mortgage", "refi", "loan broker"]),
            ("real estate", ["real estate", "realtor", "homes.com"]),
            ("plumbing", ["plumb"]),
            ("solar", ["solar"]),
            ("pest control", ["pest"]),
            ("med spa", ["med spa", "medspa"]),
            ("dental", ["dental", "dentist"]),
            ("saas", ["saas", "software as a service"]),
            ("insurance", ["insurance"]),
            ("agency", ["white-label", "marketing agency", "media agency", "knoxmedia"]),
        ]
        business_type = "unknown"
        for name, kws in biz_keywords:
            if any(k in up for k in kws):
                business_type = name
                break

        service_map = {
            "septic": "24/7 lead response + job booking",
            "roofing": "storm lead triage + booking",
            "hvac": "qualification + service call booking",
            "real estate": "AI assistant",
            "solar": "lead response + nurture",
            "personal injury": "instant response automation",
            "legal": "intake automation",
            "med spa": "DM triage",
            "mortgage": "reactivation campaign",
            "agency": "partnership / white-label",
            "insurance": "conversion lift",
        }
        needs_map = {
            "septic": ["answer 24/7", "book emergency jobs", "capture after-hours leads"],
            "roofing": ["triage storm surge", "auto-book inspections", "beat competitors to callback"],
            "hvac": ["qualify inbound", "auto-book service calls", "after-hours response"],
            "real estate": ["pricing info"],
            "personal injury": ["speed-to-lead", "beat competitors"],
            "legal": ["intake automation"],
            "solar": ["respond faster", "book site visits"],
            "mortgage": ["reactivate stale leads", "outbound at scale"],
            "med spa": ["triage DMs", "book consults"],
            "agency": ["white-label partnership"],
            "insurance": ["raise conversion rate"],
        }
        return json.dumps({
            "name": None,
            "service_requested": service_map.get(business_type),
            "urgency": "high" if is_urgent else ("low" if low_intent else "medium"),
            "budget": "$2k-$5k/mo" if "roofing" in up else (None if not has_budget else "unspecified"),
            "business_type": business_type,
            "key_needs": needs_map.get(business_type, []),
            "clean_summary": (user_prompt[:180] + "...") if len(user_prompt) > 180 else user_prompt,
        })

    if agent == "qualification":
        # Read intake metadata from the user_prompt JSON
        intake_urgency_high = '"urgency": "high"' in up
        intake_has_service = '"service_requested": "' in up and '"service_requested": null' not in up
        intake_has_business = '"business_type":' in up and '"business_type": "unknown"' not in up

        if low_intent or no_budget:
            tier, score = "Low", 18
            signals, flags = [], ["no budget", "vague intent"]
        elif is_urgent or intake_urgency_high:
            tier, score = "High", 86
            signals = ["specific pain point", "time-bound request", "clear business context"]
            flags = []
        elif intake_has_service and intake_has_business:
            tier, score = "Medium", 62
            signals = ["named business type", "identified service interest"]
            flags = ["no stated timeline"]
        else:
            tier, score = "Medium", 48
            signals = ["some context provided"]
            flags = ["no timeline", "no budget confirmed"]
        return json.dumps({
            "tier": tier,
            "intent_score": score,
            "positive_signals": signals,
            "red_flags": flags,
            "reasoning": f"Classified {tier} based on stated pain, urgency, and budget signals.",
        })

    if agent == "response":
        if upstream_tier == "Low":
            tone, msg, cta = "brief", (
                "Thanks for checking us out! In one line: we run a small team of AI agents "
                "that qualify and reply to leads for you. Want me to send a 30-second demo clip?"
            ), "Send demo clip"
        elif upstream_tier == "High":
            tone, msg, cta = "urgent", (
                "Got it — losing inbound leads is painful and totally fixable. We can stand up "
                "a follow-up agent for your business this week. I've held two call slots for you. "
                "Which works better: tomorrow 10am or Thursday 2pm?"
            ), "Book a call"
        else:
            tone, msg, cta = "consultative", (
                "Happy to share pricing. It scales with lead volume — most businesses your size "
                "land between $400 and $1,200/mo. Want me to send a one-pager tailored to your use case?"
            ), "Send pricing one-pager"
        return json.dumps({"tone": tone, "message": msg, "cta": cta})

    if agent == "followup":
        if upstream_tier == "Low":
            return json.dumps({
                "follow_up_needed": False,
                "strategy": "Add to low-priority nurture list; no active follow-up.",
                "messages": [],
            })
        return json.dumps({
            "follow_up_needed": True,
            "strategy": "Two-touch cadence over 5 days across email and SMS.",
            "messages": [
                {"when": "+48h", "channel": "email",
                 "message": "Just bumping this — still good to connect this week?"},
                {"when": "+5 days", "channel": "sms",
                 "message": "Closing the loop here. Happy to send a short demo if helpful."},
            ],
        })

    if agent == "action":
        # Pipeline value by business type (midpoint per tier)
        # (high tier, medium tier, low tier) — estimated pipeline $ per lead
        biz_values = {
            "septic":           (7800,  2800, 150),   # installs run $4k-$15k; pumping $400-$900
            "roofing":          (14500, 5200, 200),   # residential $8k-$25k, commercial much higher
            "hvac":             (11000, 3600, 180),   # new install $6k-$15k, repair $400-$2k
            "plumbing":         (4800,  1600, 100),
            "solar":            (18000, 6500, 250),
            "pest control":     (1400,  600,  80),
            "real estate":      (14000, 4500, 300),
            "legal":            (28000, 9500, 400),
            "personal injury":  (42000, 15000, 500),
            "med spa":          (3800,  1400, 120),
            "dental":           (2400,  900,  100),
            "saas":             (18000, 6500, 400),
            "agency":           (14000, 5500, 300),
            "insurance":        (2800,  1100, 100),
            "mortgage":         (8500,  3200, 200),
        }
        biz = "unknown"
        for key in biz_values:
            if f'"business_type": "{key}"' in up:
                biz = key
                break
        hi, md, lo = biz_values.get(biz, (6500, 2400, 200))

        if upstream_tier == "Low":
            return json.dumps({
                "next_action": "nurture_later",
                "priority": "P3",
                "justification": "No budget and weak intent — park on nurture list.",
                "estimated_pipeline_value_usd": lo,
            })
        if upstream_tier == "High":
            return json.dumps({
                "next_action": "escalate_to_sales",
                "priority": "P0",
                "justification": "High-intent, time-bound, clear pain — warm handoff to sales today.",
                "estimated_pipeline_value_usd": hi,
            })
        return json.dumps({
            "next_action": "send_pricing",
            "priority": "P1",
            "justification": "Interested buyer asking about pricing; send tailored one-pager.",
            "estimated_pipeline_value_usd": md,
        })

    if agent == "manager":
        if upstream_tier == "Low":
            return (
                "Low-intent inquiry with weak buying signals. Brief acknowledgment drafted; "
                "no active follow-up scheduled. Drop into long-cycle nurture."
            )
        if upstream_tier == "High":
            return (
                "High-intent lead with a clear operational pain point and stated timeline. "
                "Response drafted in an urgent tone. Warm handoff to sales today."
            )
        return (
            "Medium-intent lead asking about pricing with partial business context. "
            "Pricing response drafted. Send tailored one-pager and watch for reply inside 48h."
        )

    return "{}"
