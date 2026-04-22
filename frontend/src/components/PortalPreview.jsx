import React, { useEffect, useState } from "react";

/**
 * Read-only preview of what a paying customer would see inside Keres.
 * Example customer: Hatcher Septic & Drain (Moultrie, GA).
 *
 * All data is static demo content — clearly labeled as a preview at the top.
 */
const CUSTOMER = {
  name: "Hatcher Septic & Drain",
  location: "Moultrie, GA",
  trucks: 3,
  plan: "Growth",
  since: "Pilot — Mar 2026",
};

const TODAY_STATS = [
  { label: "Calls answered",   value: "14 / 14", sub: "100% · all resolved" },
  { label: "Jobs booked",      value: "9",        sub: "$4,820 est. revenue" },
  { label: "Avg answer time",  value: "8s",       sub: "Industry avg: 4h 12m" },
  { label: "Missed calls",     value: "0",        sub: "Last missed: Apr 19" },
  { label: "SMS sent",         value: "38",       sub: "21 ETAs · 17 follow-ups" },
  { label: "CSAT (last 30d)",  value: "4.8",      sub: "of 5 · 47 responses" },
];

const CALL_LOG = [
  { time: "06:12 AM", who: "Darlene (2295550142)",     scenario: "Emergency backup",     outcome: "Booked · Truck 3 · 6:45 AM",         tag: "P0",   revenue: 680 },
  { time: "08:03 AM", who: "Howie Keller",              scenario: "New install quote",    outcome: "Quote sent · $8,200",                tag: "WARM", revenue: 8200 },
  { time: "09:41 AM", who: "Amelia Park",               scenario: "Schedule routine pump", outcome: "Booked · Truck 1 · Apr 24",         tag: "OK",   revenue: 420 },
  { time: "10:17 AM", who: "(229) 555-0088",            scenario: "Price inquiry",        outcome: "Info sent · nurture · 30d",          tag: "COLD", revenue: 0 },
  { time: "11:04 AM", who: "Ray Kowalski",              scenario: "Follow-up on proposal", outcome: "Reminder scheduled · 48h",          tag: "OK",   revenue: 0 },
  { time: "12:38 PM", who: "Bertha Lane",               scenario: "Scheduling conflict",  outcome: "Rescheduled · Apr 25 · 9 AM",        tag: "OK",   revenue: 0 },
  { time: "01:22 PM", who: "Danny Ortega",              scenario: "Warranty question",    outcome: "Escalated to Mike · slack #ops",     tag: "ESC",  revenue: 0 },
  { time: "02:45 PM", who: "Janelle Porter",            scenario: "New customer · pump",  outcome: "Booked · Truck 2 · Apr 23",          tag: "OK",   revenue: 540 },
  { time: "04:11 PM", who: "(912) 555-0210",            scenario: "Emergency · overflow", outcome: "Booked · Truck 3 · 5:15 PM",         tag: "P0",   revenue: 720 },
];

const INBOX_ITEMS = [
  { from: "Facebook Lead Ad", name: "Carlos Ramirez",   msg: "Need septic pump, rural. What's your weekend rate?", when: "2m ago" },
  { from: "Website form",     name: "Stephanie Owens",  msg: "Looking for annual maintenance contract pricing.",  when: "14m ago" },
  { from: "Google Ad",        name: "Derek Jensen",     msg: "New build — 1,500 gal tank install quote please.",  when: "42m ago" },
  { from: "Phone inquiry",    name: "(229) 555-0166",   msg: "Voicemail · asking about commercial pumping.",      when: "1h ago" },
];

const TEAM_ALERTS = [
  { level: "ok",   title: "Truck 3 capacity hit", detail: "Marcus at 7/8 jobs booked — overflow routing to Truck 2." },
  { level: "warn", title: "Callback SLA at risk", detail: "Howie Keller quote follow-up due in 38m — auto-send queued." },
  { level: "ok",   title: "No missed calls",      detail: "14 of 14 inbound calls answered under 10s today." },
  { level: "warn", title: "Review request sent",  detail: "Darlene Hatcher · Google review · auto-asked at 8:12 AM." },
];

const INTEGRATION_HEALTH = [
  { name: "Twilio",          status: "ok", latency: "142 ms", last: "just now" },
  { name: "Google Calendar", status: "ok", latency: "210 ms", last: "2m ago"   },
  { name: "ServiceTitan",    status: "ok", latency: "380 ms", last: "4m ago"   },
  { name: "Zapier",          status: "ok", latency: "96 ms",  last: "just now" },
  { name: "HubSpot",         status: "warn", latency: "1.2 s", last: "18m ago — elevated latency" },
  { name: "SendGrid",        status: "ok", latency: "180 ms", last: "6m ago"   },
];

const TAG_CLASS = {
  P0:   "portal-tag-danger",
  WARM: "portal-tag-warn",
  OK:   "portal-tag-ok",
  ESC:  "portal-tag-alt",
  COLD: "portal-tag-muted",
};

function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export default function PortalPreview({ onExit }) {
  const now = useClock();
  const timeStr = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  const dateStr = now.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });

  return (
    <div className="portal-shell">
      <div className="portal-preview-banner">
        <span className="portal-preview-badge">Preview</span>
        <span className="portal-preview-text">
          Example customer: <strong>Hatcher Septic &amp; Drain</strong> — read-only demo of the customer portal.
        </span>
        <button className="portal-preview-exit" onClick={onExit}>← Back to demo</button>
      </div>

      <header className="portal-top">
        <div className="portal-brand">
          <div className="portal-brand-mark">KS</div>
          <div>
            <div className="portal-brand-name">Keres · {CUSTOMER.name}</div>
            <div className="portal-brand-sub">{CUSTOMER.location} · {CUSTOMER.trucks} trucks · {CUSTOMER.plan} plan · {CUSTOMER.since}</div>
          </div>
        </div>
        <div className="portal-clock">
          <div className="portal-clock-time">{timeStr}</div>
          <div className="portal-clock-date">{dateStr}</div>
        </div>
      </header>

      <div className="portal-kpis">
        {TODAY_STATS.map((s, i) => (
          <div key={i} className="portal-kpi">
            <div className="portal-kpi-label">{s.label}</div>
            <div className="portal-kpi-value">{s.value}</div>
            <div className="portal-kpi-sub">{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="portal-grid">
        <section className="portal-card portal-calllog">
          <div className="portal-card-head">
            <h3>Today's call log</h3>
            <span className="portal-card-sub">{CALL_LOG.length} calls · 0 missed</span>
          </div>
          <table className="portal-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Caller</th>
                <th>Scenario</th>
                <th>Outcome</th>
                <th>Tag</th>
              </tr>
            </thead>
            <tbody>
              {CALL_LOG.map((row, i) => (
                <tr key={i}>
                  <td className="portal-mono">{row.time}</td>
                  <td>{row.who}</td>
                  <td className="portal-dim">{row.scenario}</td>
                  <td>{row.outcome}</td>
                  <td><span className={`portal-tag ${TAG_CLASS[row.tag]}`}>{row.tag}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="portal-card">
          <div className="portal-card-head">
            <h3>Inbox · unprocessed</h3>
            <span className="portal-card-sub">{INBOX_ITEMS.length} in queue</span>
          </div>
          <div className="portal-inbox-list">
            {INBOX_ITEMS.map((lead, i) => (
              <div key={i} className="portal-inbox-row">
                <div className="portal-inbox-top">
                  <span className="portal-inbox-name">{lead.name}</span>
                  <span className="portal-inbox-when">{lead.when}</span>
                </div>
                <div className="portal-inbox-msg">{lead.msg}</div>
                <div className="portal-inbox-src">{lead.from}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="portal-card">
          <div className="portal-card-head">
            <h3>Team alerts</h3>
            <span className="portal-card-sub">{TEAM_ALERTS.filter(a => a.level === "warn").length} need attention</span>
          </div>
          <div className="portal-alerts">
            {TEAM_ALERTS.map((a, i) => (
              <div key={i} className={`portal-alert portal-alert-${a.level}`}>
                <div className="portal-alert-dot" />
                <div>
                  <div className="portal-alert-title">{a.title}</div>
                  <div className="portal-alert-detail">{a.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="portal-card">
          <div className="portal-card-head">
            <h3>Integration health</h3>
            <span className="portal-card-sub">Last 30 min</span>
          </div>
          <div className="portal-integrations">
            {INTEGRATION_HEALTH.map((i, idx) => (
              <div key={idx} className="portal-integration-row">
                <div className={`portal-dot portal-dot-${i.status}`} />
                <div className="portal-integration-name">{i.name}</div>
                <div className="portal-integration-latency">{i.latency}</div>
                <div className="portal-integration-last">{i.last}</div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <footer className="portal-foot">
        This portal is read-only in preview mode. Real customers get editable dispatch boards, review responses, billing exports, and per-agent tuning.
      </footer>
    </div>
  );
}
