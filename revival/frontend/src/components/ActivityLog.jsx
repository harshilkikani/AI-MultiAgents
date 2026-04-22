import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const EVENT_ICON = {
  "campaign.created": "🎬",
  "campaign.paused": "⏸",
  "campaign.resumed": "▶",
  "campaign.paid": "💳",
  "lead.inbound_classified": "📨",
  "message.sent": "✉️",
  "message.failed": "⚠️",
  "owner_alert.fired": "🔔",
  "jobber.sync": "🔄",
  "compliance.opt_out": "🛑",
};

function fmt(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

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
  if (!events) return <div className="lr-muted">Loading activity…</div>;

  return (
    <div className="lr-activity">
      <div className="lr-activity-filter">
        <label>Filter:</label>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All events</option>
          <option value="campaign.paused">Campaign paused</option>
          <option value="campaign.resumed">Campaign resumed</option>
          <option value="lead.inbound_classified">Inbound replies</option>
          <option value="message.sent">Outbound sends</option>
          <option value="jobber.sync">Jobber syncs</option>
        </select>
        <span className="lr-muted" style={{ marginLeft: "auto" }}>{events.length} events</span>
      </div>

      {events.length === 0 && (
        <div className="lr-muted lr-activity-empty">No events yet for this filter.</div>
      )}

      <ul className="lr-activity-list">
        {events.map((ev) => (
          <li key={ev.id} className="lr-activity-event">
            <span className="lr-activity-icon">{EVENT_ICON[ev.event_type] || "•"}</span>
            <div className="lr-activity-body">
              <div className="lr-activity-head">
                <span className="lr-activity-type">{ev.event_type}</span>
                <span className="lr-activity-when">{fmt(ev.created_at)}</span>
              </div>
              {ev.summary && <div className="lr-activity-summary">{ev.summary}</div>}
              <div className="lr-activity-meta">
                <span>by {ev.actor_type}{ev.actor_id ? ` (${ev.actor_id})` : ""}</span>
                {ev.lead_id && <span>lead #{ev.lead_id}</span>}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
