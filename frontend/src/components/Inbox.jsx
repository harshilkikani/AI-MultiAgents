import React from "react";

const SOURCE_ICONS = {
  "website form": "🌐",
  "facebook lead ad": "📘",
  "instagram dm": "📸",
  "linkedin message": "💼",
  "google ad": "🔎",
  "email reply": "✉️",
  "cold email reply": "✉️",
  "phone inquiry": "📞",
  "referral": "🤝",
  "newsletter": "📰",
};

function timeAgo(arrivedAt, now) {
  const diff = Math.max(0, Math.floor((now - arrivedAt) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function Inbox({ inbox, activeLeadId, onSelect, now }) {
  const unread = inbox.filter((l) => !l.processed).length;

  return (
    <div className="card inbox-card">
      <div className="card-head">
        <h2>Inbox</h2>
        <span className="pill">{unread} unread · {inbox.length} total</span>
      </div>

      <div className="inbox-list">
        {inbox.length === 0 && (
          <div className="empty-state">
            Click <strong>Start Demo</strong> to begin receiving leads.
          </div>
        )}
        {inbox.map((lead) => {
          const isActive = lead.id === activeLeadId;
          const isProcessing = lead.processing;
          return (
            <button
              key={lead.id}
              className={
                "inbox-item" +
                (isActive ? " active" : "") +
                (lead.processed ? " processed" : "") +
                (isProcessing ? " processing" : "")
              }
              onClick={() => onSelect(lead)}
            >
              <div className="inbox-item-head">
                <span className="source-icon">{SOURCE_ICONS[lead.source] || "📨"}</span>
                <span className="inbox-name">{lead.contact_name || "Anonymous"}</span>
                <span className="inbox-time">{timeAgo(lead.arrivedAt, now)}</span>
              </div>
              <div className="inbox-preview">{lead.message}</div>
              <div className="inbox-foot">
                <span className="inbox-source">{lead.source || "unknown"}</span>
                {lead.processed && lead.tier && (
                  <span className={`pill ${lead.tier.toLowerCase()}`}>{lead.tier}</span>
                )}
                {isProcessing && (
                  <span className="pill running">
                    <span className="spinner" /> processing
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
