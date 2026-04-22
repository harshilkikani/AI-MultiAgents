# Lead Revival

Dead-lead revival SaaS for home-services shops. Upload an old-leads CSV,
our 6-agent Claude pipeline drafts personalized revival SMS, drips them
over 4 weeks via Twilio, classifies replies, and reports recovered
revenue.

**Pricing:** $1,500 one-shot per campaign · $499/mo always-on · carrier
SMS passes through at $0.01 markup.

**Lives:** on the `lead-revival` branch under `revival/` in the
`harshilkikani/AI-MultiAgents` repo. The top-level `backend/` and
`frontend/` directories are the MultiAgents demo and stay untouched.

---

## Quickstart — local (DEMO mode, no API keys)

```bash
# Backend
cd revival/backend
python -m venv .venv && source .venv/Scripts/activate    # Windows bash
# source .venv/bin/activate                              # macOS/Linux
pip install -r requirements.txt
cp .env.example .env                                     # DEMO_MODE=true by default
python scripts/gen_sample_csv.py                         # regenerates fixtures/sample_leads.csv (idempotent)
python -m scripts.seed_demo                              # optional — seeds the Hatcher Septic demo workspace
uvicorn app.main:app --reload --port 8001

# Frontend (new terminal)
cd revival/frontend
npm install
npm run dev                                              # http://localhost:5174
```

Open http://localhost:5174/demo to see the read-only Hatcher Septic example,
or http://localhost:5174 to kick off your own campaign.

## Quickstart — Docker

```bash
cd revival
docker compose up --build
# backend: http://localhost:8001
# frontend: http://localhost:5174
```

## Tests

```bash
cd revival/backend
pytest -q                           # all backend tests (currently 47)
```

Frontend has no automated tests yet — Vite build serves as the smoke check
in CI (`npm run build`).

## Environment variables

All secrets are optional in `DEMO_MODE=true`. Set them only when you're
ready to send real SMS / charge real cards.

| var                          | purpose                                      |
| ---------------------------- | -------------------------------------------- |
| `DEMO_MODE`                  | `true` disables all external calls           |
| `DATABASE_URL`               | SQLite dev default; swap in Postgres for prod|
| `CORS_ORIGINS`               | comma-separated frontend origins             |
| `ANTHROPIC_API_KEY`          | Claude API — generation + reply classifier   |
| `TWILIO_ACCOUNT_SID`         | Twilio SID for outbound SMS                  |
| `TWILIO_AUTH_TOKEN`          | Twilio auth token                            |
| `TWILIO_FROM_NUMBER`         | E.164 number Twilio sends from               |
| `STRIPE_SECRET_KEY`          | Stripe API key for Checkout                  |
| `STRIPE_WEBHOOK_SECRET`      | Stripe webhook signing secret                |
| `STRIPE_PRICE_ONE_SHOT`      | Stripe price id for $1,500 one-shot          |
| `STRIPE_PRICE_MONTHLY`       | Stripe price id for $499 monthly             |
| `DISABLE_SCHEDULER`          | `1` in tests — stops APScheduler from ticking|

## Architecture

```
        CSV upload ─▶ Campaign ─▶ RevivalPipeline (6-agent or templates)
                                           │
                                           ▼
                                 Messages × 4 per lead
                                (Day-0 / Day-3 / Day-10 / Day-24)
                                           │
                       ┌───────────────────┼───────────────────┐
                       ▼                                       ▼
                APScheduler tick/15min                 Twilio inbound webhook
                       │                                       │
                       ▼                                       ▼
                  Twilio send                      Reply classifier (haiku)
                       │                                       │
                       ▼                                       ▼
               Lead.state advances            State transitions + auto-reply
                                                      (Calendly link on yes)
                                                               │
                                                               ▼
                                                  Calendly webhook → booked
```

### Lead state machine

- `queued` → `contacted` (Day-0 sent)
- `contacted` → `replied_hot` (yes intent) → auto-reply Calendly link
- `replied_hot` → `booked` (Calendly webhook)
- `contacted` → `replied_no` (no intent) — pending messages cancelled
- `contacted` → `opted_out` (STOP / UNSUBSCRIBE) — pending cancelled
- `contacted` → `dead` (no reply after Day-24) — set by a future cleanup task

### Drip cadence (per lead)

| Step   | When         | Tone                                  |
| ------ | ------------ | ------------------------------------- |
| Day-0  | t=0          | Soft reopen — reference original ask  |
| Day-3  | t+72h        | Gentle bump                           |
| Day-10 | t+240h       | Seasonal / urgency hook               |
| Day-24 | t+576h       | Final offer, graceful close           |

Quiet hours: 8am–7pm local time, via an area-code → IANA timezone map.
Unknown area codes default to `America/New_York`.

## Milestones shipped

| milestone | commit prefix              |
| --------- | -------------------------- |
| M1        | `M1 (revival): scaffold…`  |
| M2        | `M2 (revival): pipeline…`  |
| M3        | `M3 (revival): Twilio…`    |
| M4        | `M4 (revival): scheduler…` |
| M5        | `M5 (revival): booking…`   |
| M6        | `M6 (revival): dashboard…` |
| M7        | `M7 (revival): workspace…` |
| M8        | `M8 (revival): Stripe…`    |
| M9        | `M9 (revival): demo…`      |
| M10       | `M10 (revival): deploy…`   |

## Deploying

### Fly.io (backend)

```bash
cd revival
fly launch --config fly.toml --copy-config --no-deploy   # first time only
fly secrets set ANTHROPIC_API_KEY=... TWILIO_ACCOUNT_SID=... ...
fly volumes create revival_data --region iad --size 1
fly deploy
```

### Vercel / Netlify (frontend)

Build command: `npm run build` · Output dir: `dist` · Root directory:
`revival/frontend`.

Set `VITE_PROXY_TARGET=https://your-fly-app.fly.dev` if you want
`npm run dev` to proxy to prod, or override the API base at runtime.

## Before going live — TODO

These are the TCPA + security guardrails the MVP leaves as stubs:

- [ ] **Twilio webhook signature verification** (validate `X-Twilio-Signature`)
- [ ] **Calendly webhook signature verification**
- [ ] **Stripe webhook replay-timestamp check** — current verifier checks HMAC but not freshness
- [ ] **TCPA opt-out audit log** — persist STOP events with timestamp + proof
- [ ] **Frequency caps** — hard stop if a phone already received 5 revival SMS in 30 days
- [ ] **Real multi-tenancy auth** (Supabase magic-link or similar) — today uses `X-Workspace-Id` header only
- [ ] **Prompt caching verification** — confirm cache-hit rates in the Anthropic dashboard before scaling

## Continuous improvement backlog

After M10, these are the next refinements ranked by prospect impact:

1. **Fuzzy CSV column matching** — today we match exact aliases; add edit-distance fallback so nonstandard headers from bespoke CRMs still map cleanly.
2. **Per-vertical template library** — one revival_system.txt for all five verticals is fine but leaves prompt-cache efficiency on the table; per-vertical system blocks would cache better.
3. **A/B-test two drip cadences** — let a campaign ship with Variant A and Variant B messages, track reply rate per variant.
4. **Direct Jobber/ServiceTitan ingest** — replace CSV upload with an OAuth-authed read against the CRM API.
5. **Owner mobile alerts for hot replies** — SMS or push the shop owner when a lead goes `replied_hot`.
