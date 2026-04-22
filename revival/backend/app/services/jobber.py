# Why this exists: Jobber OAuth + cold-lead ingest. CSVs are fine for a
# pilot, but recurring revenue means recurring data — this module lets us
# pull old leads directly from the shop's Jobber account on a cron.
#
# In DEMO_MODE, `connect_*` returns a fake token and `sync_cold_leads`
# synthesizes deterministic demo rows so the end-to-end flow works without
# hitting Jobber. Real mode talks to their GraphQL API.
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Campaign, JobberConnection, Lead
from app.services.audit import record as audit_record
from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("jobber")

JOBBER_AUTHORIZE_URL = "https://api.getjobber.com/api/oauth/authorize"
JOBBER_TOKEN_URL = "https://api.getjobber.com/api/oauth/token"
JOBBER_API_URL = "https://api.getjobber.com/api/graphql"

JOBBER_SCOPES = "read_clients read_requests read_jobs read_quotes"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# ------------------------------------------------------------
# OAuth
# ------------------------------------------------------------
def build_authorize_url(state: str) -> str:
    """URL to send the owner to for Jobber's consent screen."""
    s = get_settings()
    if not s.jobber_client_id:
        raise RuntimeError("JOBBER_CLIENT_ID not configured (set in .env or use DEMO_MODE)")
    params = {
        "client_id": s.jobber_client_id,
        "redirect_uri": s.jobber_redirect_uri,
        "response_type": "code",
        "scope": JOBBER_SCOPES,
        "state": state,
    }
    return f"{JOBBER_AUTHORIZE_URL}?{urlencode(params)}"


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[datetime]
    scopes: Optional[str]
    account_name: Optional[str]


def exchange_code_for_token(code: str) -> TokenBundle:
    """Swap the one-time OAuth code for an access + refresh token pair."""
    s = get_settings()
    if s.demo_mode:
        return TokenBundle(
            access_token=f"demo-jobber-{code[:12]}",
            refresh_token=f"demo-refresh-{code[:12]}",
            expires_at=_now() + timedelta(hours=6),
            scopes=JOBBER_SCOPES,
            account_name="Demo Jobber Shop",
        )
    import httpx
    r = httpx.post(JOBBER_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": s.jobber_client_id,
        "client_secret": s.jobber_client_secret,
        "redirect_uri": s.jobber_redirect_uri,
    }, timeout=15.0)
    r.raise_for_status()
    body = r.json()
    expires_in = int(body.get("expires_in") or 0)
    return TokenBundle(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_at=_now() + timedelta(seconds=expires_in) if expires_in else None,
        scopes=body.get("scope"),
        account_name=None,
    )


def save_connection(db: Session, workspace_id: int, tokens: TokenBundle) -> JobberConnection:
    existing = db.scalars(
        select(JobberConnection).where(JobberConnection.workspace_id == workspace_id)
    ).first()
    if existing:
        existing.access_token = tokens.access_token
        existing.refresh_token = tokens.refresh_token
        existing.expires_at = tokens.expires_at
        existing.scopes = tokens.scopes
        existing.account_name = tokens.account_name or existing.account_name
        existing.status = "active"
        existing.connected_at = _now()
        row = existing
    else:
        row = JobberConnection(
            workspace_id=workspace_id,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=tokens.expires_at,
            scopes=tokens.scopes,
            account_name=tokens.account_name,
            status="active",
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def disconnect(db: Session, workspace_id: int) -> bool:
    row = db.scalars(
        select(JobberConnection).where(JobberConnection.workspace_id == workspace_id)
    ).first()
    if not row:
        return False
    row.status = "disconnected"
    row.access_token = "revoked"
    row.refresh_token = None
    db.commit()
    return True


# ------------------------------------------------------------
# Sync
# ------------------------------------------------------------
@dataclass
class SyncResult:
    pulled: int          # raw rows seen
    inserted: int        # new leads added (after dedup)
    skipped: int         # rows we couldn't use (no phone/email, too recent, etc.)
    already_present: int # rows matched an existing Lead via external_id


def _iter_cold_leads_demo(campaign: Campaign, cutoff: date, rng: random.Random) -> list[dict]:
    """Deterministic fake cold leads for DEMO mode. Stable per campaign +
    last-synced-at window, so repeated syncs dedup cleanly."""
    out: list[dict] = []
    sources = ["Jobber form", "Jobber phone", "Jobber referral"]
    first_names = ["Dale", "Priya", "Brian", "Tina", "Howie", "Amelia", "Marcus",
                   "Janelle", "Carlos", "Wanda", "Lamar", "Reba", "Gus", "Doris"]
    last_names = ["Hatcher", "Shah", "Holt", "Browne", "Keller", "Park", "Lane",
                  "Porter", "Ramirez", "Harmon", "Ruiz", "Stanton", "Holcomb"]
    for i in range(20):  # 20 per sync
        fn = rng.choice(first_names); ln = rng.choice(last_names)
        # Use name as seed for a stable external_id so re-syncs dedup.
        ext_id = hashlib.md5(f"jobber-{fn}-{ln}-{i}-{campaign.id}".encode()).hexdigest()[:16]
        ac = rng.choice([229, 404, 303, 602, 713, 215, 412])
        phone = f"+1{ac}555{rng.randint(1000, 9999):04d}"
        age_days = rng.randint(90, 450)
        out.append({
            "external_id": f"client_{ext_id}",
            "name": f"{fn} {ln}",
            "phone": phone,
            "email": f"{fn.lower()}.{ln.lower()}@ex.com" if rng.random() > 0.4 else None,
            "source": rng.choice(sources),
            "last_contact": (date.today() - timedelta(days=age_days)).isoformat(),
            "notes": rng.choice([
                "Requested quote, never closed.",
                "Asked for maintenance pricing, went quiet.",
                "Had an emergency, we couldn't get there that day.",
                "Price-shopped, picked someone else.",
            ]),
        })
    return out


def _iter_cold_leads_real(conn: JobberConnection, cutoff: date) -> list[dict]:
    """Real GraphQL query against Jobber. Pulls clients with requests older
    than `cutoff` that never became jobs.

    NOTE: the real query will differ slightly per Jobber account; owners may
    need to grant additional scopes. If the shape breaks in prod, the caller
    catches the exception and surfaces it via /api/integrations/jobber/sync.
    """
    import httpx
    query = """
    query ColdLeads($since: Date!) {
      clients(filter: { lastActivityAt: { before: $since } }, first: 100) {
        nodes {
          id
          name
          phones { number isMobile }
          emails { address }
          firstName
          lastName
          createdAt
          companyName
          tags
        }
      }
    }
    """
    headers = {
        "Authorization": f"Bearer {conn.access_token}",
        "X-JOBBER-GRAPHQL-VERSION": "2024-09-18",
        "Content-Type": "application/json",
    }
    r = httpx.post(
        JOBBER_API_URL,
        json={"query": query, "variables": {"since": cutoff.isoformat()}},
        headers=headers,
        timeout=30.0,
    )
    r.raise_for_status()
    body = r.json()
    out: list[dict] = []
    for n in ((body.get("data") or {}).get("clients") or {}).get("nodes", []):
        phones = [p for p in (n.get("phones") or []) if p.get("number")]
        phone = (phones[0] or {}).get("number") if phones else None
        emails = [e.get("address") for e in (n.get("emails") or []) if e.get("address")]
        out.append({
            "external_id": n.get("id"),
            "name": n.get("name") or f"{n.get('firstName') or ''} {n.get('lastName') or ''}".strip() or "(unknown)",
            "phone": phone,
            "email": emails[0] if emails else None,
            "source": "Jobber",
            "last_contact": (n.get("createdAt") or "")[:10] or None,
            "notes": None,
        })
    return out


def sync_cold_leads(
    db: Session,
    *,
    workspace_id: int,
    campaign_id: int,
    cutoff_days: int = 180,
) -> SyncResult:
    """Pull cold leads from Jobber into the given campaign. Dedup key is
    `(external_source='jobber', external_id)` on the leads table, so this
    is safe to call on a cron."""
    conn = db.scalars(
        select(JobberConnection).where(
            JobberConnection.workspace_id == workspace_id,
            JobberConnection.status == "active",
        )
    ).first()
    if conn is None:
        raise ValueError("no active Jobber connection for this workspace — connect first")

    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.workspace_id != workspace_id:
        raise ValueError("campaign not found in workspace")

    cutoff = date.today() - timedelta(days=cutoff_days)

    # Use a hash of campaign_id + last_synced_at day to seed the demo RNG so
    # the SAME (or very similar) rows come back on a same-day re-sync —
    # which exercises the dedup path.
    if get_settings().demo_mode:
        seed_key = f"{campaign.id}-{(conn.last_synced_at or conn.connected_at).date().isoformat()}"
        rng = random.Random(int(hashlib.md5(seed_key.encode()).hexdigest(), 16))
        rows = _iter_cold_leads_demo(campaign, cutoff, rng)
    else:
        rows = _iter_cold_leads_real(conn, cutoff)

    pulled = len(rows)
    inserted = 0
    already = 0
    skipped = 0

    for row in rows:
        ext_id = row.get("external_id")
        if not ext_id:
            skipped += 1
            continue
        existing = db.scalars(
            select(Lead).where(
                Lead.workspace_id == workspace_id,
                Lead.external_source == "jobber",
                Lead.external_id == ext_id,
            )
        ).first()
        if existing is not None:
            already += 1
            continue

        # Basic contact sanity — need at least phone OR email.
        if not (row.get("phone") or row.get("email")):
            skipped += 1
            continue

        # Parse last_contact to a date, tolerant to missing or malformed.
        lc: Optional[date] = None
        lc_raw = row.get("last_contact")
        if lc_raw:
            try:
                lc = date.fromisoformat(lc_raw)
            except Exception:
                lc = None

        db.add(Lead(
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            name=row.get("name") or "(unknown)",
            phone=row.get("phone"),
            email=row.get("email"),
            source=row.get("source") or "Jobber",
            last_contact=lc,
            notes=row.get("notes"),
            external_source="jobber",
            external_id=str(ext_id),
        ))
        inserted += 1

    result = SyncResult(
        pulled=pulled, inserted=inserted, skipped=skipped, already_present=already,
    )
    conn.last_synced_at = _now()
    conn.last_sync_stats = {
        "pulled": result.pulled, "inserted": result.inserted,
        "skipped": result.skipped, "already_present": result.already_present,
        "synced_at": conn.last_synced_at.isoformat(),
    }
    audit_record(
        db,
        workspace_id=workspace_id, campaign_id=campaign.id,
        event_type="jobber.sync", actor_type="system",
        summary=f"Jobber sync: {inserted} new · {already} already present · {skipped} skipped",
        meta=conn.last_sync_stats,
    )
    db.commit()
    return result
