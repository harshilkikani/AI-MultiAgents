# Why this exists: inbound SMS replies need to be classified into
# {yes, no, maybe, stop, other} so the state machine and scheduler know
# what to do. DEMO_MODE uses keyword heuristics; real mode delegates to
# Claude haiku with prompt caching.
from __future__ import annotations

import re
from typing import Literal

from app.utils.logger import get_logger
from app.utils.parser import extract_json
from app.utils.settings import get_settings

log = get_logger("classifier")

Intent = Literal["yes", "no", "maybe", "stop", "other"]

# TCPA / industry-standard opt-out keywords. These MUST classify as 'stop'
# regardless of surrounding noise.
_STOP_KEYWORDS = {"stop", "stopall", "unsubscribe", "cancel", "quit", "end", "remove"}

# Short-circuit heuristics used in DEMO_MODE and as a pre-filter in real mode
# (save a Claude call when the signal is obvious).
_YES_PATTERNS = [
    r"\byes\b", r"\byeah\b", r"\byep\b", r"\bsure\b", r"\bok\b", r"\bokay\b",
    r"\blet'?s do it\b", r"\bgo ahead\b", r"\bi'?m in\b", r"\bplease\b",
    r"\bsounds good\b", r"\bbook (me|it)\b", r"\bsend (the|it|me)\b",
    r"\bwhen\b.*\bcome\b", r"\btonight\b", r"\btomorrow\b", r"\bthis week\b",
    r"\bquote\b.*\bplease\b", r"\bget (started|going)\b",
]
_NO_PATTERNS = [
    r"\bno\b(?! (thanks|problem))", r"\bnot interested\b", r"\bnot now\b",
    r"\bwrong number\b", r"\bwho is this\b", r"\balready (done|fixed|handled|hired)\b",
    r"\bwent with\b", r"\bpass\b", r"\bno thanks\b",
]
_MAYBE_PATTERNS = [
    r"\bmaybe\b", r"\bperhaps\b", r"\bthinking\b", r"\bconsidering\b",
    r"\bhow much\b", r"\bprice\b", r"\bcost\b", r"\bcall me\b",
    r"\bnext (week|month)\b", r"\blater\b", r"\bquestion\b",
]


def _keyword_classify(body: str) -> Intent:
    raw = (body or "").strip()
    if not raw:
        return "other"
    low = raw.lower()
    # Stop must win — TCPA compliance.
    tokens = set(re.findall(r"[a-z]+", low))
    if tokens & _STOP_KEYWORDS:
        return "stop"
    for pat in _YES_PATTERNS:
        if re.search(pat, low):
            return "yes"
    for pat in _NO_PATTERNS:
        if re.search(pat, low):
            return "no"
    for pat in _MAYBE_PATTERNS:
        if re.search(pat, low):
            return "maybe"
    return "other"


_CLASSIFIER_SYSTEM = (
    "You classify a one-message SMS reply to a home-services revival campaign. "
    "Return ONLY a JSON object: {\"intent\": <one of yes, no, maybe, stop, other>}. "
    "Rules:\n"
    "- yes: the lead wants to move forward (booking, quote, call)\n"
    "- no: the lead explicitly declines, wrong number, already handled\n"
    "- maybe: asking for info, pricing, timing without committing\n"
    "- stop: TCPA opt-out (STOP, UNSUBSCRIBE, CANCEL, etc.)\n"
    "- other: greetings, thanks, unrelated chatter, emojis only\n"
)


def classify_reply(body: str) -> Intent:
    """Fast path: obvious keyword matches return immediately. Ambiguous
    messages go to haiku (in real mode) or fall back to 'other' (in demo)."""
    heuristic = _keyword_classify(body)
    if heuristic != "other":
        return heuristic

    if get_settings().demo_mode:
        return "other"

    # Real mode: ask haiku for the ambiguous case.
    try:
        from app.utils.llm_client import CLASSIFIER_MODEL, call_claude
        raw = call_claude(
            system_prompt=_CLASSIFIER_SYSTEM,
            user_prompt=f"REPLY:\n{body}\n\nReturn the JSON object only.",
            max_tokens=50,
            model=CLASSIFIER_MODEL,
            use_cache=True,
        )
        data = extract_json(raw)
        intent = str(data.get("intent", "other")).lower()
        if intent in {"yes", "no", "maybe", "stop", "other"}:
            return intent  # type: ignore[return-value]
    except Exception as e:
        log.warning("classifier LLM fallback failed: %s", e)
    return "other"
