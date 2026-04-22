import React from "react";

// Status distribution is intentionally conservative — on a sales call we can
// honestly say a few are live, a few are in beta with pilot customers, and
// the rest ship in the Q2 2026 integration wave.
const INTEGRATIONS = [
  { name: "Twilio",          mark: "TW", color: "#f22f46", status: "live",  desc: "Answer calls, send SMS, and stream voice transcripts through your Twilio numbers." },
  { name: "Google Calendar", mark: "GC", color: "#4285f4", status: "live",  desc: "Book jobs and appointments directly on your team's Google Calendar." },
  { name: "Zapier",          mark: "ZP", color: "#ff4f00", status: "live",  desc: "Trigger 6,000+ downstream apps from any Keres event — webhook-first." },

  { name: "ServiceTitan",    mark: "ST", color: "#1f7a3e", status: "beta",  desc: "Push jobs, calls, and customer records to your ServiceTitan tenant in real time." },
  { name: "Jobber",          mark: "JB", color: "#0b5cff", status: "beta",  desc: "Sync quotes, jobs, and invoices with Jobber — bi-directional." },
  { name: "HubSpot",         mark: "HS", color: "#ff7a59", status: "beta",  desc: "Create contacts, deals, and tasks in HubSpot CRM as leads qualify." },

  { name: "Housecall Pro",   mark: "HP", color: "#1d6feb", status: "q2",    desc: "Two-way sync for customers, jobs, and payments." },
  { name: "Service Fusion",  mark: "SF", color: "#e94e1b", status: "q2",    desc: "Bi-directional sync for dispatch, scheduling, and job history." },
  { name: "FieldEdge",       mark: "FE", color: "#0a64a4", status: "q2",    desc: "Mirror inbound calls and work orders into FieldEdge." },
  { name: "RingCentral",     mark: "RC", color: "#ff7a00", status: "q2",    desc: "Auto-answer and intelligently route calls from your RingCentral numbers." },
  { name: "Outlook",         mark: "OL", color: "#0078d4", status: "q2",    desc: "Two-way sync with Outlook / Microsoft 365 calendars." },
  { name: "Make",            mark: "MK", color: "#6d00cc", status: "q2",    desc: "Wire Keres into Make (Integromat) scenarios as a trigger or action." },
];

const STATUS_LABEL = {
  live: "Live",
  beta: "Beta",
  q2:   "Q2 2026",
};

export default function Integrations() {
  return (
    <section className="integrations-card card" aria-labelledby="integrations-heading">
      <div className="card-head">
        <h2 id="integrations-heading">Integrations</h2>
        <span className="pill">
          {INTEGRATIONS.filter((i) => i.status === "live").length} live ·{" "}
          {INTEGRATIONS.filter((i) => i.status === "beta").length} beta ·{" "}
          {INTEGRATIONS.filter((i) => i.status === "q2").length} shipping Q2 2026
        </span>
      </div>
      <div className="integrations-grid">
        {INTEGRATIONS.map((i) => (
          <div key={i.name} className="integration-tile" tabIndex={0}>
            <div className="integration-logo" style={{ background: i.color }}>{i.mark}</div>
            <div className="integration-name">{i.name}</div>
            <span className={`integration-status integration-${i.status}`}>
              {STATUS_LABEL[i.status]}
            </span>
            <div className="integration-tooltip" role="tooltip">{i.desc}</div>
          </div>
        ))}
      </div>
      <div className="integrations-foot">
        Don't see your stack? Keres speaks generic webhooks + CSV out of the box — most one-off integrations go live during onboarding.
      </div>
    </section>
  );
}
