# Why this exists: real CRM exports have inconsistent column names. This
# module maps common headers to our canonical field names and normalizes
# phone/date/strings so the rest of the app deals with one clean shape.
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

# Canonical fields we want on a Lead.
CANON_FIELDS = ("name", "phone", "email", "source", "last_contact", "notes")

# Header aliases (lowercase, stripped). Supports the three big CRMs:
# Jobber, ServiceTitan, HubSpot — plus generic "name" / "phone".
HEADER_ALIASES: dict[str, str] = {
    # name
    "name": "name", "customer": "name", "customer_name": "name",
    "contact": "name", "contact_name": "name", "full_name": "name",
    "client": "name", "client_name": "name",
    # phone
    "phone": "phone", "phone_number": "phone", "phone_no": "phone",
    "mobile": "phone", "mobile_phone": "phone", "cell": "phone",
    "cell_phone": "phone", "primary_phone": "phone", "home_phone": "phone",
    # email
    "email": "email", "email_address": "email", "primary_email": "email",
    # source
    "source": "source", "lead_source": "source", "origin": "source",
    "campaign_source": "source", "referral_source": "source",
    # last_contact
    "last_contact": "last_contact", "last_contacted": "last_contact",
    "last_contact_date": "last_contact", "last_activity": "last_contact",
    "last_activity_date": "last_contact", "created": "last_contact",
    "created_at": "last_contact", "date": "last_contact",
    "created_date": "last_contact",
    # notes
    "notes": "notes", "note": "notes", "comments": "notes",
    "description": "notes", "details": "notes", "job_notes": "notes",
}


@dataclass
class NormalizedLead:
    name: str
    phone: Optional[str]
    email: Optional[str]
    source: Optional[str]
    last_contact: Optional[date]
    notes: Optional[str]


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def _norm_phone(raw: Optional[str]) -> Optional[str]:
    """Strip non-digits, keep a leading + if present; validate 10-15 digits."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    # Default US: 10-digit bare → +1 prefix
    if len(digits) == 10 and not plus:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1") and not plus:
        return f"+{digits}"
    if 10 <= len(digits) <= 15:
        return f"+{digits}" if plus or len(digits) > 10 else f"+1{digits}"
    return None


_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d",
    "%m/%d/%Y", "%m-%d-%Y",
    "%m/%d/%y", "%m-%d-%y",
    "%d/%m/%Y", "%d-%m-%Y",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
)


def _norm_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Fast path: ISO-ish
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _norm_str(raw: Optional[str], max_len: int = 500) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    return s[:max_len] if s else None


def _norm_email(raw: Optional[str]) -> Optional[str]:
    s = _norm_str(raw)
    if not s:
        return None
    # Cheap sanity check — avoid eating CSV-level garbage as an email.
    if "@" not in s or "." not in s.split("@")[-1]:
        return None
    return s.lower()


def build_header_map(headers: list[str]) -> dict[str, str]:
    """Return {canonical_field: actual_header}. Missing = not in output.

    Matching is layered:
      1. Exact alias match (fast path, via HEADER_ALIASES).
      2. Fuzzy match (edit distance / difflib) for headers that didn't
         exact-match. This catches "Customer_Name" vs "customer name",
         "Primary-Phone" vs "Primary Phone", unpredictable CSV exports.
    """
    import difflib

    out: dict[str, str] = {}
    unmatched: list[str] = []
    for h in headers:
        canon = HEADER_ALIASES.get(_norm_header(h))
        if canon and canon not in out:
            out[canon] = h
        else:
            unmatched.append(h)

    # Fuzzy pass — try to fit leftover headers into still-missing canonical
    # slots. cutoff=0.7 catches "frst nm" → "first_name" without wild
    # false positives.
    missing_canons = [c for c in CANON_FIELDS if c not in out]
    alias_keys = list(HEADER_ALIASES.keys())
    for h in unmatched:
        normed = _norm_header(h)
        if not normed:
            continue
        matches = difflib.get_close_matches(normed, alias_keys, n=1, cutoff=0.72)
        if matches:
            canon = HEADER_ALIASES[matches[0]]
            if canon in missing_canons:
                out[canon] = h
                missing_canons.remove(canon)
    return out


def header_map_override(headers: list[str], override: dict[str, str]) -> dict[str, str]:
    """Apply user-supplied mapping. Keys are canonical fields; values are
    the actual header names. Unknown / blank values are dropped."""
    out: dict[str, str] = {}
    for canon, actual in (override or {}).items():
        if canon not in CANON_FIELDS:
            continue
        if actual and actual in headers:
            out[canon] = actual
    return out


def parse_csv(
    content: bytes | str,
    override_mapping: Optional[dict[str, str]] = None,
) -> tuple[list[NormalizedLead], list[str]]:
    """Parse a CSV blob. Returns (leads, skipped_reasons).

    A row is skipped if it has no name, or has neither phone nor email.
    Pass `override_mapping` to force specific header-to-canonical bindings
    (from the mapping-confirm UI step).
    """
    leads, skipped, _headers, _hm = _parse_csv_full(content, override_mapping)
    return leads, skipped


def _parse_csv_full(
    content: bytes | str,
    override_mapping: Optional[dict[str, str]] = None,
) -> tuple[list[NormalizedLead], list[str], list[str], dict[str, str]]:
    """Internal: returns leads, skipped, all headers, and the effective
    header mapping so callers can show it to the user."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig", errors="replace")

    reader = csv.DictReader(io.StringIO(content))
    headers = list(reader.fieldnames or [])
    if not headers:
        return [], ["csv has no header row"], [], {}

    header_map = build_header_map(headers)
    # Overlay any explicit override from the UI (user may correct fuzzy
    # mismatches or pick a different column).
    if override_mapping:
        header_map = {**header_map, **header_map_override(headers, override_mapping)}

    if "name" not in header_map:
        return (
            [],
            [f"could not find a 'name' column; saw: {headers}"],
            headers,
            header_map,
        )

    leads: list[NormalizedLead] = []
    skipped: list[str] = []
    for i, row in enumerate(reader, start=2):  # line 2 = first data row
        name = _norm_str(row.get(header_map["name"]), max_len=200)
        phone = _norm_phone(row.get(header_map["phone"])) if "phone" in header_map else None
        email = _norm_email(row.get(header_map["email"])) if "email" in header_map else None
        source = _norm_str(row.get(header_map["source"]), max_len=100) if "source" in header_map else None
        last_contact = _norm_date(row.get(header_map["last_contact"])) if "last_contact" in header_map else None
        notes = _norm_str(row.get(header_map["notes"]), max_len=2000) if "notes" in header_map else None

        if not name:
            skipped.append(f"line {i}: missing name")
            continue
        if not phone and not email:
            skipped.append(f"line {i}: no phone or email for {name}")
            continue

        leads.append(NormalizedLead(
            name=name, phone=phone, email=email, source=source,
            last_contact=last_contact, notes=notes,
        ))
    return leads, skipped, headers, header_map


def preview_csv(
    content: bytes | str,
    override_mapping: Optional[dict[str, str]] = None,
    preview_limit: int = 10,
) -> dict:
    """Parse + summarize a CSV WITHOUT persisting. Used by the mapping UI
    so owners can eyeball header detection before committing 5k rows."""
    leads, skipped, headers, header_map = _parse_csv_full(content, override_mapping)
    return {
        "all_headers": headers,
        "mapping": header_map,
        "unmapped_headers": [h for h in headers if h not in header_map.values()],
        "canonical_fields": list(CANON_FIELDS),
        "total_valid": len(leads),
        "total_skipped": len(skipped),
        "skipped_reasons": skipped[:20],
        "preview": [
            {
                "name": l.name, "phone": l.phone, "email": l.email,
                "source": l.source,
                "last_contact": l.last_contact.isoformat() if l.last_contact else None,
                "notes": l.notes,
            }
            for l in leads[:preview_limit]
        ],
    }
