import React from "react";

const STATE_META = {
  queued:      { label: "Queued",      color: "var(--muted)" },
  contacted:   { label: "Contacted",   color: "var(--keres)" },
  replied_hot: { label: "Hot",         color: "var(--warn)" },
  replied_no:  { label: "Declined",    color: "var(--muted-2)" },
  booked:      { label: "Booked",      color: "var(--ok)" },
  dead:        { label: "Dead",        color: "var(--muted-2)" },
  opted_out:   { label: "Opted out",   color: "var(--danger)" },
};

export default function StateCounts({ counts, onPick, selected }) {
  const entries = Object.entries(STATE_META);
  return (
    <div className="lr-state-counts">
      {entries.map(([key, meta]) => {
        const n = counts?.[key] ?? 0;
        const active = selected === key;
        return (
          <button
            key={key}
            className={"lr-state-pill" + (active ? " active" : "")}
            onClick={() => onPick?.(active ? null : key)}
            style={{ "--pill-color": meta.color }}
          >
            <span className="lr-state-label">{meta.label}</span>
            <span className="lr-state-value">{n}</span>
          </button>
        );
      })}
    </div>
  );
}
