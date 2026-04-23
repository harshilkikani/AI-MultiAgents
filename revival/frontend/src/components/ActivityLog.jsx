import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// event_type → (icon, human label, color class). Falls through to
// raw-code display for anything we haven't labeled yet.
const EVENT_META = {
  "campaign.created":       { icon: "🎬", label: "Campaign created",    tone: "info" },
  "campaign.paused":        { icon: "⏸",  label: "Campaign paused",     tone: "warn" },
  "campaign.resumed":       { icon: "▶",  label: "Campaign resumed",    tone: "ok" },
  "campaign.paid":          { icon: "💳", label: "Campaign paid",       tone: "ok" },
  "lead.inbound_classified":{ icon: "📨", label: "Inbound reply",       tone: "info" },
  "message.sent":           { icon: "✉️", label: "SMS sent",            tone: "ok" },
  "message.failed":         { icon: "⚠️", label: "Send failed",         tone: "err" },
  "message.cancelled":      { icon: "✕",  label: "Message cancelled",   tone: "muted" },
  "owner_alert.fired":      { icon: "🔔", label: "Owner alerted",       tone: "warn" },
  "jobber.sync":            { icon: "🔄", label: "Jobber sync",         tone: "info" },
  "compliance.opt_out":     { icon: "🛑", label: "Opt-out recorded",    tone: "err" },
  "compliance.blocked":     { icon: "🚫", label: "Compliance block",    tone: "err" },
};

function fmt(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  const diffH = (Date.now() - d.getTime()) / 3_600_000;
  if (diffH < 1)  return `${Math.max(0, Math.floor(diffH * 60))}m ago`;
  if (diffH < 24) return `${Math.floor(diffH)}h ago`;
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

const FILTERS = [
  { value: "", label: "All events" },
  { value: "campaign.paused", label: "Campaign paused" },
  { value: "campaign.resumed", label: "Campaign resumed" },
  { value: "lead.inbound_classified", label: "Inbound replies" },
  { value: "message.sent", label: "Outbound sends" },
  { value: "jobber.sync", label: "Jobber syncs" },
  { value: "compliance.opt_out", label: "Opt-outs (TCPA)" },
];

export default function ActivityLog({ campaignId }) {
  const [events, setEvents] = useState(null);
  const [filter, setFilter] = useState("");
  const [err, setErr] = useState(null);

  useEffect(() => {
    setEvents(null);
    setErr(null);
    api.campaignAudit(campaignId, filter || undefined)
      .then(setEvents)
      .catch((e) => setErr(e.message));
  }, [campaignId, filter]);

  if (err) return <div className="lr-error">{err}</div>;

  return (
    <div className="lr-activity">
      <div className="lr-activity-filter">
        <label htmlFor="lr-activity-filter-select">Filter:</label>
        <select
          id="lr-activity-filter-select"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {FILTERS.map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
        <span className="lr-muted" style={{ marginLeft: "auto" }}>
          {events ? `${events.length} event${events.length === 1 ? "" : "s"}` : "—"}
        </span>
      </div>

      {!events && (
        <div className="lr-skeleton">
          <div className="lr-skel-line lr-skel-w80" />
          <div className="lr-skel-line lr-skel-w60" />
          <div className="lr-skel-line lr-skel-w40" />
        </div>
      )}
      {events && events.length === 0 && (
        <div className="lr-muted lr-activity-empty">
          No events yet{filter ? ` for "${FILTERS.find((f) => f.value === filter)?.label}"` : ""}.
          Kick off a send or reply to see activity here.
        </div>
      )}

      {events && events.length > 0 && (
        <ul className="lr-activity-list">
          {events.map((ev) => {
            const meta = EVENT_META[ev.event_type] || { icon: "•", label: ev.event_type, tone: "muted" };
            return (
              <li key={ev.id} className={`lr-activity-event lr-activity-${meta.tone}`}>
                <span className="lr-activity-icon" aria-hidden="true">{meta.icon}</span>
                <div className="lr-activity-body">
                  <div className="lr-activity-head">
                    <span className="lr-activity-type">{meta.label}</span>
                    <span className="lr-activity-when" title={ev.created_at}>{fmt(ev.created_at)}</span>
                  </div>
                  {ev.summary && <div className="lr-activity-summary">{ev.summary}</div>}
                  <div className="lr-activity-meta">
                    <span>by {ev.actor_type}{ev.actor_id ? ` (${ev.actor_id})` : ""}</span>
                    {ev.lead_id && <span>lead #{ev.lead_id}</span>}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
