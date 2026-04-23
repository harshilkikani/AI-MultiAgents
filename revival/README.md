# Lead Revival

Dead-lead revival SaaS for home-services shops. Upload an old-leads CSV (or
connect Jobber directly), a vertical-tuned Claude prompt drafts revival
SMS, drips them over 4 weeks via Twilio, classifies replies, alerts the
shop owner the moment a lead goes hot, and reports recovered revenue.

**Pricing** · $1,500 one-shot per campaign · $499/mo always-on · carrier
SMS passes through at $0.01 markup.

**Branch** · this code lives on `lead-revival` in the
`harshilkikani/AI-MultiAgents` repo, under the `revival/` subtree. The
parent repo's top-level `backend/` and `frontend/` are the MultiAgents
demo and stay untouched.

---

## Quickstart — local (DEMO mode, no API keys)

```bash
# Backend
cd revival/backend
python -m venv .venv && source .venv/Scripts/activate    # Windows bash
# source .venv/bin/activate                              # macOS/Linux
pip install -r requirements.txt
cp .env.example .env                                     # DEMO_MODE=true by default
python scripts/gen_sample_csv.py                         # regenerates fixtures/sample_leads.csv
python -m scripts.seed_demo                              # optional — seeds the Hatcher Septic demo workspace
uvicorn app.main:app --reload --port 8001

# Frontend (new terminal)
cd revival/frontend
npm install
npm run dev                                              # http://localhost:5174
```

- http://localhost:5174/login — magic-link login (DEMO returns an instant stub token).
- http://localhost:5174/demo — read-only preview of the seeded "Hatcher Septic" workspace.
- http://localhost:5174 — upload a CSV and run your own campaign.

## Quickstart — Docker

```bash
cd revival
docker compose up --build
# backend  → http://localhost:8001
# frontend → http://localhost:5174
```

## Tests

```bash
cd revival/backend
pytest -q                           # 108 backend tests · 4 warnings
```

Frontend has no automated tests yet — Vite `npm run build` is the smoke
check in CI. A Playwright pass is on the backlog.

## Database migrations

Alembic lives in `revival/backend/migrations/`. On every deploy, Fly runs
`alembic upgrade head` via the `release_command` in `fly.toml`. Locally:

```bash
cd revival/backend
alembic upgrade head                  # apply pending migrations
alembic revision --autogenerate -m "add x"
alembic downgrade -1                  # roll back one
```

`init_db()` remains as a dev-mode shortcut that calls `Base.metadata.create_all()`.
A schema-drift test (`test_init_db_and_alembic_agree_on_schema`) fails if
a new ORM column ships without a matching migration.

## Environment variables

Everything is optional in `DEMO_MODE=true`. Set them only when leaving DEMO.

### Core
| var                | purpose                                                  |
| ------------------ | -------------------------------------------------------- |
| `DEMO_MODE`        | `true` disables all external calls                       |
| `DATABASE_URL`     | SQLite for dev, `postgresql+psycopg://…` for prod        |
| `CORS_ORIGINS`     | comma-separated frontend origins                         |
| `DISABLE_SCHEDULER`| `1` disables the APScheduler loop (tests, one-off dev)   |

### Claude / Twilio / Stripe
| var                                | purpose                                        |
| ---------------------------------- | ---------------------------------------------- |
| `ANTHROPIC_API_KEY`                | Claude API — generation + reply classifier    |
| `CLAUDE_MODEL`                     | override generation model (default opus-4-7)  |
| `CLAUDE_CLASSIFIER_MODEL`          | override classifier model (default haiku-4-5) |
| `TWILIO_ACCOUNT_SID` + `_AUTH_TOKEN` + `_FROM_NUMBER` | outbound SMS + inbound signature validation |
| `STRIPE_SECRET_KEY` + `_WEBHOOK_SECRET`               | Checkout + webhook                          |
| `STRIPE_PRICE_ONE_SHOT` / `_MONTHLY`                  | Stripe price ids                            |

### Webhooks (M12)
| var                        | purpose                                              |
| -------------------------- | ---------------------------------------------------- |
| `CALENDLY_WEBHOOK_SECRET`  | HMAC secret for `/webhooks/calendly` signature check |

### Auth (M13)
| var                    | purpose                                                           |
| ---------------------- | ----------------------------------------------------------------- |
| `SUPABASE_JWT_SECRET`  | HS256 shared secret — validate Bearer JWTs                        |
| `SUPABASE_URL`         | Supabase project URL (for `/api/auth/login` magic-link dispatch)  |
| `SUPABASE_ANON_KEY`    | public anon key (Supabase OTP endpoint auth)                      |

### Jobber (M18)
| var                        | purpose                                                |
| -------------------------- | ------------------------------------------------------ |
| `JOBBER_CLIENT_ID`         | OAuth client id (dev.getjobber.com)                    |
| `JOBBER_CLIENT_SECRET`     | OAuth client secret                                    |
| `JOBBER_REDIRECT_URI`      | must match the redirect URI configured in Jobber       |

### Observability (M20)
| var            | purpose                                      |
| -------------- | -------------------------------------------- |
| `SENTRY_DSN`   | wire Sentry; blank = no-op                   |
| `SENTRY_ENV`   | `prod` / `staging` / `dev` (default `dev`)   |

### Testing-only
| var                     | purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `REVIVAL_TEST_BYPASS=1` | skip all webhook signature verification (CI + tests) |

## Architecture

```
                    CSV or Jobber sync
                             │
                             ▼
                        Lead table  ──┐
                             │         │ (per workspace, per vertical, tone-notes)
                             ▼         │
                  Revival pipeline ◀───┘
              (per-vertical system prompt + tone)
                             │
                             ▼
                  4 Message rows per lead
                  (Day-0 / Day-3 / Day-10 / Day-24)
                             │
             ┌───────────────┴───────────────────────┐
             ▼                                       ▼
     APScheduler (every 15m)              Twilio inbound webhook
     ├─ quiet hours (lead TZ)             ├─ signature verified (M12)
     ├─ TCPA compliance (opt-out /        ├─ reply classifier (haiku)
     │  DNC / freq cap, M11)              └─ state transition + audit
     └─ audit event write (M20)
             │                                       │
             ▼                                       ▼
         Twilio send                       On "yes" intent →
             │                             ├─ auto-reply Calendly
             │                             ├─ fire owner alert (M16)
             │                             └─ cancel remaining drip
             ▼
     Owner alert (M16)
     ├─ SMS to owner phone (in owner quiet hours → skip)
     └─ Slack webhook (always if configured)
             │
             ▼
     Calendly webhook (M5, signed in M12)
     └─ lead.state → booked  →  second owner alert
```

## Lead state machine

```
queued ─▶ contacted ─▶ replied_hot ─▶ booked
                  ├──▶ replied_no             (terminal)
                  ├──▶ opted_out              (TCPA, global per workspace)
                  └──▶ dead                   (no reply after Day-24)
```

## Drip cadence

| Step   | When    | Tone                                  | STOP footer? |
| ------ | ------- | ------------------------------------- | ------------ |
| Day-0  | t=0     | Soft reopen, "Reply STOP to opt out." | Yes (full)   |
| Day-3  | t+72h   | Gentle bump                           | No           |
| Day-10 | t+240h  | Seasonal / time-bound hook            | Short reminder |
| Day-24 | t+576h  | Final offer, graceful close           | No           |

Quiet hours: 8am–7pm local. Lead tz from NANP area-code map; unknown →
`America/New_York`. Owner alerts use the owner's configured tz.

## Compliance (TCPA)

Every outbound send is gated by `services/compliance.can_send()`:

1. **Opt-out** — `opt_outs` table, scoped per workspace + phone. Once a
   phone says STOP, no campaign in that workspace ever messages it again.
2. **DNC** — `data/dnc_deny.txt` local deny list. Swap for a SAN-registered
   DNC API when the first paying customer lands.
3. **Frequency cap** — max 5 SMS / 30 days per workspace + phone.

Every block is recorded in `compliance_events`. Every state transition
is recorded in `audit_events` (M20) and viewable per campaign at
`/api/campaigns/:id/audit`.

## Milestones shipped

| ms  | summary |
| --- | ------- |
| M1  | scaffold · FastAPI 8001 · Vite 5174 · CSV upload · 200-row fixture |
| M2  | revival pipeline · 4 messages per lead · prompt caching (M19 split) |
| M3  | Twilio send + inbound webhook · reply classifier (yes/no/maybe/stop) |
| M4  | APScheduler tick · quiet hours per area-code TZ |
| M5  | booking · yes auto-replies Calendly link · `/webhooks/calendly` → booked |
| M6  | dashboard · campaign list · ROI report (printable) |
| M7  | workspace scaffolding (plumbing for M13) |
| M8  | Stripe stub + billing gate · 10-lead trial |
| M9  | demo seed · public `/demo` route · Hatcher Septic example |
| M10 | Dockerfiles · docker-compose · fly.toml · GitHub Actions CI |
| **M11** | **TCPA layer** — opt_outs, freq cap, DNC, compliance_events, STOP footer |
| **M12** | **webhook sigs** — Twilio RequestValidator · Calendly HMAC+replay · Stripe construct_event |
| **M13** | **auth** — Supabase HS256 JWT · users + workspace_members · login page |
| **M14** | **Postgres + Alembic** — baseline `0001` · psycopg3 · CI runs on real Postgres |
| **M15** | **CSV mapping + sample gate** — two-step preview/commit · fuzzy headers · 3 samples before bulk |
| **M16** | **owner alerts** — hot/booked SMS + Slack · 4h dedup · owner quiet hours |
| **M17** | **pause/resume + iMessage thread UI** — bubbles · delivery statuses · strikethrough cancelled |
| **M18** | **Jobber OAuth** — direct cold-lead sync · dedup via external_id · demo-mode fake sync |
| **M19** | **per-vertical prompts + tone_notes** — 5 vertical .txt files · owner tone override via PATCH |
| **M20** | **Sentry + audit + health** — audit_events · scheduler_last_tick · /api/health 503 when stale |

## Deploying

### Fly.io (backend)

```bash
cd revival
fly launch --config fly.toml --copy-config --no-deploy   # first time only
fly volumes create revival_data --region iad --size 1
fly secrets set \
  DEMO_MODE=false \
  DATABASE_URL=... \
  ANTHROPIC_API_KEY=... \
  TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=... TWILIO_FROM_NUMBER=... \
  STRIPE_SECRET_KEY=... STRIPE_WEBHOOK_SECRET=... \
  STRIPE_PRICE_ONE_SHOT=... STRIPE_PRICE_MONTHLY=... \
  CALENDLY_WEBHOOK_SECRET=... \
  SUPABASE_JWT_SECRET=... SUPABASE_URL=... SUPABASE_ANON_KEY=... \
  JOBBER_CLIENT_ID=... JOBBER_CLIENT_SECRET=... JOBBER_REDIRECT_URI=... \
  SENTRY_DSN=... SENTRY_ENV=prod
fly deploy
```

Fly's `release_command` (`alembic upgrade head`) runs before the new
revision goes live.

### Vercel / Netlify (frontend)

- Build command: `npm run build`
- Output dir: `dist`
- Root directory: `revival/frontend`
- Proxy: set the backend URL via `VITE_PROXY_TARGET` for local dev.

## Before paying customers — remaining TODO

The hard-blocking bits (webhook signatures, TCPA, auth, migrations) are
**done** in M11–M14. What's left:

- [ ] **Real DNC integration** — swap `data/dnc_deny.txt` for a SAN-registered API call.
- [ ] **Stripe live keys** — wire the real `STRIPE_SECRET_KEY` + webhook secret and flip `DEMO_MODE=false` in staging.
- [ ] **Per-vertical prompt pilot review** — current prompts are best-guesses; let pilot customers read + tweak before their first send.
- [ ] **Hot-reply owner mobile alert testing** — Twilio + Slack both wired; confirm delivery latency < 10s in staging.
- [ ] **Playwright frontend smoke tests** — Upload → Campaign → Thread → ROI report → Audit.

## Where things live

```
revival/
├── README.md  ← you are here
├── docker-compose.yml
├── fly.toml
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── migrations/           # 0001 → 0006
│   └── app/
│       ├── main.py           # FastAPI entrypoint, auth middleware, Sentry init
│       ├── db.py             # SQLAlchemy engine + init_db (dev)
│       ├── models/
│       │   ├── orm.py        # 12 tables
│       │   └── schemas.py    # Pydantic
│       ├── prompts/          # revival_system.txt + 5 per-vertical .txt
│       ├── routes/           # 14 routers
│       ├── services/         # 14 services (agents/, alerts, audit, billing, compliance, …)
│       ├── tests/            # 12 test files, 108 tests
│       └── utils/            # logger, parser, settings, llm_client
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── Dockerfile            # multi-stage Vite build → Caddy
    └── src/
        ├── main.jsx · App.jsx · api.js · auth.js · ws.js · styles.css
        ├── pages/            # Upload, CampaignList, CampaignDetail, RoiReport, Demo, Settings, Login
        └── components/       # LeadTable, MessageThread, StateCounts, MappingTable,
                              #  JobberPanel, ActivityLog, HealthDot
```
