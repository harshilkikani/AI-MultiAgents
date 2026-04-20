# Keres — AI Lead Automation for Septic, Roofing & HVAC

**Keres is an AI workforce for home-services contractors.** It qualifies, replies to, and routes every inbound lead — from website forms, Facebook Lead Ads, Instagram DMs, phone inquiries, and email — in under 60 seconds. Built for septic, roofing, and HVAC companies that are losing jobs to slow response times.

Six specialist AI agents work under one orchestrator to process each lead end-to-end: **Intake → Qualification → Response → Follow-Up → Action → Manager**.

---

## What this repo contains

An MVP demo of the Keres multi-agent platform. A single orchestrator coordinates six specialist Claude-powered agents that take a raw business lead and output a full decision package: structured intake, qualification score, drafted response, follow-up cadence, recommended next action, and an executive summary for the business owner.

Built to feel like an **AI workforce** — not a chatbot.

---

## Architecture

```
                 ┌────────────────────────────────────────┐
  Lead input ──▶ │        Orchestrator / Manager          │ ──▶  Final decision
                 └────────────────────────────────────────┘
                                │
         ┌──────────┬───────────┼───────────┬──────────────┐
         ▼          ▼           ▼           ▼              ▼
     Intake   Qualification  Response    Follow-Up    Action Rec.
     Agent       Agent        Agent       Agent         Agent
```

Each agent:
- has its own system prompt (in `backend/app/prompts/`)
- returns **structured JSON** validated by a Pydantic model
- is invoked by the orchestrator in sequence, with the previous outputs as context

The Manager Agent reads the full pipeline and writes a plain-English summary.

---

## Project layout

```
AI_MultiAgents/
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py
│       ├── routes/
│       │   └── agent_routes.py
│       ├── services/
│       │   ├── orchestrator.py
│       │   └── agents/
│       │       ├── base.py
│       │       ├── intake_agent.py
│       │       ├── qualification_agent.py
│       │       ├── response_agent.py
│       │       ├── followup_agent.py
│       │       ├── action_agent.py
│       │       └── manager_agent.py
│       ├── prompts/
│       │   ├── intake_prompt.txt
│       │   ├── qualification_prompt.txt
│       │   ├── response_prompt.txt
│       │   ├── followup_prompt.txt
│       │   ├── action_prompt.txt
│       │   └── manager_prompt.txt
│       ├── models/schemas.py
│       └── utils/
│           ├── llm_client.py
│           ├── parser.py
│           ├── logger.py
│           └── demo_responses.py
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        ├── styles.css
        └── components/
            ├── LeadForm.jsx
            ├── AgentCard.jsx
            └── Results.jsx
```

---

## Local setup

### 1. Backend

Requires Python 3.10+.

```bash
cd backend
python -m venv .venv
# Windows (bash):
source .venv/Scripts/activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# then edit .env and paste your ANTHROPIC_API_KEY

uvicorn app.main:app --reload --port 8000
```

Backend runs at http://localhost:8000. Swagger UI at http://localhost:8000/docs.

**Demo mode (no API key):** set `DEMO_MODE=true` in `.env`. The system will return deterministic, believable canned outputs — perfect for demos and offline development.

### 2. Frontend

Requires Node 18+.

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` to the FastAPI server on port 8000.

---

## API

### `POST /api/process-lead`

**Request body (`LeadInput`)**
```json
{
  "message": "Hi, I need help automating follow-up for my roofing company...",
  "source": "website form",
  "budget": "$2k-$5k/mo",
  "service_requested": "lead follow-up automation",
  "urgency": "high"
}
```

**Response (`FinalDecisionOutput`)**
```json
{
  "lead_input": { ... },
  "intake": {
    "name": null,
    "service_requested": "lead follow-up automation",
    "urgency": "high",
    "budget": "$2k-$5k/mo",
    "business_type": "roofing",
    "key_needs": ["automate follow-up", "capture missed leads"],
    "clean_summary": "Roofing business owner wants help automating follow-up..."
  },
  "qualification": {
    "tier": "High",
    "intent_score": 86,
    "positive_signals": ["specific pain point", "time-bound request"],
    "red_flags": [],
    "reasoning": "Clear pain, budget signal, and an explicit timeline..."
  },
  "response": {
    "tone": "urgent",
    "message": "Got it — losing inbound leads is painful and totally fixable...",
    "cta": "Book a call"
  },
  "follow_up": {
    "follow_up_needed": true,
    "strategy": "Two-touch cadence over 5 days across email and SMS.",
    "messages": [
      { "when": "+48h", "channel": "email", "message": "Just bumping this..." },
      { "when": "+5 days", "channel": "sms", "message": "Closing the loop..." }
    ]
  },
  "action": {
    "next_action": "escalate_to_sales",
    "priority": "P0",
    "justification": "High-intent, time-bound, clear pain — warm handoff today."
  },
  "manager_summary": "High-intent lead with a clear operational pain point...",
  "logs": [
    { "agent": "Intake Agent", "status": "ok", "duration_ms": 812 },
    { "agent": "Qualification Agent", "status": "ok", "duration_ms": 734 },
    ...
  ]
}
```

### `GET /api/sample-leads`

Returns 5 canned demo leads used by the frontend's "Sample leads" chips.

---

## Demo use cases

The frontend ships with 5 sample leads:
1. **High-intent** — roofing company wants follow-up automation this week
2. **Medium-intent** — real-estate business asking about pricing
3. **Low-intent** — "Just curious what this does."
4. **Urgent** — "We need something ASAP. Sales team is drowning."
5. **Unqualified** — "No budget right now but maybe later."

Click a chip to load, then hit **Run Agents** to watch the pipeline resolve.

---

## Future upgrades

- **CRM integration** — push final decisions into HubSpot / Salesforce / Attio with the recommended `next_action` as a task and the drafted response as a note.
- **Twilio + email sending** — actually send the response and scheduled follow-ups (Twilio SMS, SendGrid email, Gmail API) instead of only drafting them.
- **Lead memory** — a vector store (pgvector / Pinecone) so the Intake Agent can recognize returning contacts and the Response Agent can personalize based on prior conversations.
- **Analytics dashboard** — aggregate agent output: conversion rate by tier, response-to-booking ratio, most common red flags, average time-to-first-touch.
- **Human-in-the-loop** — an "approve / edit / send" gate before drafted messages go out, plus a feedback signal that fine-tunes the prompt library.
- **Parallel fan-out** — run Response and Follow-Up in parallel once Qualification completes, to cut latency.
- **Per-tenant prompt overrides** — let each business customize tone and action rules without touching code.
- **Streaming UI** — stream each agent's output to the browser as it arrives, instead of waiting for the full pipeline.
- **Webhook triggers** — accept inbound leads from Typeform / website forms / Zapier directly, so the system runs autonomously 24/7.

---

## Notes for demos

- Leave `DEMO_MODE=true` when you don't want to burn API credits or risk network flakiness in front of a customer.
- The sample leads are designed to exercise each branch of the decision tree — run all 5 to show the system adapting.
- The "Agent Run Log" at the bottom of the results panel is the best way to communicate the orchestration story to non-technical viewers.
