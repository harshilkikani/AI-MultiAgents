import React from "react";

// title attrs double as tooltips when an owner hovers — no magic state-name
// decoding required.
const STATE_META = {
  queued:      { label: "Queued",    color: "var(--muted)",    title: "Hasn't received the Day-0 SMS yet." },
  contacted:   { label: "Contacted", color: "var(--keres)",    title: "Day-0 sent · drip in flight." },
  replied_hot: { label: "Hot",       color: "var(--warn)",     title: "Said yes. Calendly link sent; waiting on booking." },
  replied_no:  { label: "Declined",  color: "var(--muted-2)",  title: "Said no / wrong number. Drip cancelled." },
  booked:      { label: "Booked",    color: "var(--ok)",       title: "Calendly slot confirmed. Revenue counted." },
  dead:        { label: "Dead",      color: "var(--muted-2)",  title: "No reply after Day-24. Closed out." },
  opted_out:   { label: "Opted out", color: "var(--danger)",   title: "STOP / UNSUBSCRIBE. Never message again." },
};

export default function StateCounts({ counts, onPick, selected }) {
  const entries = Object.entries(STATE_META);
  return (
    <div className="lr-state-counts" role="group" aria-label="Filter leads by state">
      {entries.map(([key, meta]) => {
        const n = counts?.[key] ?? 0;
        const active = selected === key;
        return (
          <button
            key={key}
            className={"lr-state-pill" + (active ? " active" : "")}
            onClick={() => onPick?.(active ? null : key)}
            style={{ "--pill-color": meta.color }}
            title={meta.title}
            aria-pressed={active}
          >
            <span className="lr-state-label">{meta.label}</span>
            <span className="lr-state-value">{n}</span>
          </button>
        );
      })}
    </div>
  );
}
