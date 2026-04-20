import React from "react";

const ICONS = {
  email_sent: "✉️",
  sms_queued: "💬",
  slack_ping: "🔔",
  calendly: "📅",
  crm_task: "📋",
  nurture: "💤",
};

const COLORS = {
  email_sent: "#7ee787",
  sms_queued: "#7c9cff",
  slack_ping: "#f5c26b",
  calendly: "#5eead4",
  crm_task: "#c4a7ff",
  nurture: "#8a94b0",
};

function timeAgo(ts, now) {
  const diff = Math.max(0, Math.floor((now - ts) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function ActivityFeed({ events, now }) {
  return (
    <div className="card activity-card">
      <div className="card-head">
        <h2>Live Activity</h2>
        <span className="pill">{events.length} events</span>
      </div>
      <div className="activity-list">
        {events.length === 0 && (
          <div className="empty-state">
            Execution events will appear here — emails sent, SMS queued, calls booked, sales notified.
          </div>
        )}
        {events.map((ev, i) => (
          <div key={ev.id || i} className="activity-item">
            <div className="activity-icon" style={{ color: COLORS[ev.kind] }}>{ICONS[ev.kind] || "●"}</div>
            <div className="activity-body">
              <div className="activity-title">
                {ev.title}
                <span className="activity-time">{timeAgo(ev.ts, now)}</span>
              </div>
              {ev.detail && <div className="activity-detail">{ev.detail}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
