# Why this exists: TCPA and plain-decency guardrail — don't SMS someone at
# 2am. Maps US area codes to a primary IANA timezone and checks if the
# current time is within the 8am-7pm local send window. Non-US or unknown
# area codes default to America/New_York (arbitrary but conservative for
# Eastern business hours).
from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

# Area code → IANA timezone. Covers ~all US area codes; truncated to the
# ones we use in fixtures + the top-40 metros. Full map can land in
# refinement — this is defensible v0.
AREA_CODE_TZ: dict[str, str] = {
    # Georgia
    "229": "America/New_York", "404": "America/New_York", "470": "America/New_York",
    "678": "America/New_York", "706": "America/New_York", "762": "America/New_York",
    "770": "America/New_York", "912": "America/New_York",
    # Colorado (all MT)
    "303": "America/Denver", "719": "America/Denver", "720": "America/Denver",
    "970": "America/Denver",
    # Arizona (no DST — hence Phoenix, not Denver)
    "480": "America/Phoenix", "520": "America/Phoenix", "602": "America/Phoenix",
    "623": "America/Phoenix", "928": "America/Phoenix",
    # Texas (most are CT; El Paso is MT — 915)
    "214": "America/Chicago", "281": "America/Chicago", "346": "America/Chicago",
    "409": "America/Chicago", "430": "America/Chicago", "432": "America/Chicago",
    "469": "America/Chicago", "512": "America/Chicago", "682": "America/Chicago",
    "713": "America/Chicago", "737": "America/Chicago", "806": "America/Chicago",
    "817": "America/Chicago", "830": "America/Chicago", "832": "America/Chicago",
    "903": "America/Chicago", "936": "America/Chicago", "940": "America/Chicago",
    "956": "America/Chicago", "972": "America/Chicago", "979": "America/Chicago",
    "915": "America/Denver",
    # Pennsylvania
    "215": "America/New_York", "267": "America/New_York", "412": "America/New_York",
    "484": "America/New_York", "610": "America/New_York", "717": "America/New_York",
    "724": "America/New_York", "814": "America/New_York", "878": "America/New_York",
    # California (PT)
    "209": "America/Los_Angeles", "213": "America/Los_Angeles", "310": "America/Los_Angeles",
    "323": "America/Los_Angeles", "408": "America/Los_Angeles", "415": "America/Los_Angeles",
    "424": "America/Los_Angeles", "510": "America/Los_Angeles", "559": "America/Los_Angeles",
    "619": "America/Los_Angeles", "626": "America/Los_Angeles", "650": "America/Los_Angeles",
    "661": "America/Los_Angeles", "707": "America/Los_Angeles", "714": "America/Los_Angeles",
    "747": "America/Los_Angeles", "760": "America/Los_Angeles", "805": "America/Los_Angeles",
    "818": "America/Los_Angeles", "858": "America/Los_Angeles", "909": "America/Los_Angeles",
    "916": "America/Los_Angeles", "925": "America/Los_Angeles", "949": "America/Los_Angeles",
    "951": "America/Los_Angeles",
    # New York
    "212": "America/New_York", "315": "America/New_York", "347": "America/New_York",
    "516": "America/New_York", "585": "America/New_York", "607": "America/New_York",
    "631": "America/New_York", "646": "America/New_York", "716": "America/New_York",
    "718": "America/New_York", "845": "America/New_York", "914": "America/New_York",
    "917": "America/New_York", "929": "America/New_York",
    # Florida
    "305": "America/New_York", "321": "America/New_York", "352": "America/New_York",
    "386": "America/New_York", "407": "America/New_York", "561": "America/New_York",
    "727": "America/New_York", "754": "America/New_York", "772": "America/New_York",
    "786": "America/New_York", "813": "America/New_York", "850": "America/Chicago",
    "863": "America/New_York", "904": "America/New_York", "941": "America/New_York",
    "954": "America/New_York",
}

_DEFAULT_TZ = "America/New_York"
QUIET_START_HOUR = 8   # 8:00 AM local — earliest send
QUIET_END_HOUR = 19    # 7:00 PM local — latest send


def _area_code_for(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    # Expect E.164 like "+12295550142". US country code is 1, NPA is next 3.
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) >= 11 and digits.startswith("1"):
        return digits[1:4]
    if len(digits) == 10:
        return digits[:3]
    return None


def tz_for_phone(phone: Optional[str]) -> ZoneInfo:
    ac = _area_code_for(phone)
    return ZoneInfo(AREA_CODE_TZ.get(ac, _DEFAULT_TZ))


def is_within_quiet_window(phone: Optional[str], now_utc: Optional[datetime] = None) -> bool:
    """Return True if it's OK to send now (i.e., NOT in quiet hours)."""
    tz = tz_for_phone(phone)
    now = now_utc or datetime.now(tz=ZoneInfo("UTC"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    local = now.astimezone(tz)
    return QUIET_START_HOUR <= local.hour < QUIET_END_HOUR


def is_within_owner_window(
    tz_name: Optional[str],
    now_utc: Optional[datetime] = None,
) -> bool:
    """Owner-alert variant: check quiet hours against an explicit IANA tz
    name (stored on the workspace). Unknown/blank → ET default."""
    try:
        tz = ZoneInfo(tz_name) if tz_name else ZoneInfo(_DEFAULT_TZ)
    except Exception:
        tz = ZoneInfo(_DEFAULT_TZ)
    now = now_utc or datetime.now(tz=ZoneInfo("UTC"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    local = now.astimezone(tz)
    return QUIET_START_HOUR <= local.hour < QUIET_END_HOUR
