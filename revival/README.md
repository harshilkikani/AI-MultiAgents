# Lead Revival

Dead-lead revival SaaS for home-services shops. Upload an old-leads CSV,
a 6-agent Claude pipeline drafts personalized revival messages, drips
them via Twilio SMS over 4 weeks, classifies replies, and reports
recovered revenue.

Lives on the `lead-revival` branch under `revival/` in the AI_MultiAgents
repo. The top-level `backend/` and `frontend/` directories are the
MultiAgents demo and stay untouched.

## Quickstart (M1)

### Backend
```bash
cd revival/backend
python -m venv .venv
source .venv/Scripts/activate        # Windows bash
# source .venv/bin/activate          # macOS/Linux
pip install -r requirements.txt
cp .env.example .env                 # DEMO_MODE=true by default
python scripts/gen_sample_csv.py     # only needed once; regenerates fixtures/sample_leads.csv
uvicorn app.main:app --reload --port 8001
```

### Frontend
```bash
cd revival/frontend
npm install
npm run dev                          # http://localhost:5174
```

Open http://localhost:5174 → **Upload** → drop `revival/backend/fixtures/sample_leads.csv`
→ see 200 leads ingested.

### Tests
```bash
cd revival/backend
pytest -q
```

## Milestones shipped
- **M1** — Scaffold + CSV upload (this commit)

## Milestones remaining
- M2 — Revival agent pipeline (generate 4 messages per lead)
- M3 — Twilio send + inbound webhook (reply classifier)
- M4 — Scheduler (drip cadence + quiet hours)
- M5 — Booking (Calendly auto-reply)
- M6 — Dashboard + ROI report
- M7 — Workspace scaffolding (multi-tenancy plumbing)
- M8 — Stripe stub + billing gate
- M9 — Demo seed + public `/demo` route
- M10 — Deploy config (Dockerfiles, docker-compose, Fly.io, CI)

## Env vars (see `.env.example`)
| var | purpose |
|---|---|
| `DEMO_MODE` | `true` disables all external calls — seed data + UI still work |
| `DATABASE_URL` | SQLite for dev, Postgres later |
| `CORS_ORIGINS` | comma-separated list; defaults to `http://localhost:5174` |
| `ANTHROPIC_API_KEY` | ignored when DEMO_MODE |
| `TWILIO_*` | ignored when DEMO_MODE |
| `STRIPE_*` | ignored when DEMO_MODE |

## Ports
Backend **8001**, frontend **5174** — so it doesn't collide with the
parent MultiAgents demo on 8000 / 5173.
