import React, { useEffect, useState } from "react";
import { api } from "../api.js";

function fmtTs(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

const STEP_LABEL = {
  "-1": "Inbound",
  0: "Day 0",
  1: "Day 3",
  2: "Day 10",
  3: "Day 24",
  99: "Auto-reply",
};

export default function MessageThread({ campaignId, lead, onClose }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null);
    setErr(null);
    if (!lead) return;
    api.leadMessages(campaignId, lead.id).then(setData).catch((e) => setErr(e.message));
  }, [campaignId, lead?.id]);

  if (!lead) return null;

  return (
    <div className="lr-modal-backdrop" onClick={onClose}>
      <div className="lr-modal" onClick={(e) => e.stopPropagation()}>
        <div className="lr-modal-head">
          <div>
            <div className="lr-modal-title">{lead.name}</div>
            <div className="lr-modal-sub">{lead.phone || "—"} · {lead.source || "—"} · state: {lead.state}</div>
          </div>
          <button className="lr-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="lr-thread">
          {err && <div className="lr-error">{err}</div>}
          {!data && !err && <div className="lr-muted">Loading…</div>}
          {data?.messages.map((m) => (
            <div key={m.id} className={"lr-msg " + (m.direction === "in" ? "lr-msg-in" : "lr-msg-out")}>
              <div className="lr-msg-head">
                <span className="lr-msg-step">{STEP_LABEL[m.step] ?? `step ${m.step}`}</span>
                <span className="lr-msg-status">{m.status}</span>
                <span className="lr-msg-when">{m.sent_at ? fmtTs(m.sent_at) : (m.scheduled_for ? `→ ${fmtTs(m.scheduled_for)}` : "")}</span>
              </div>
              <div className="lr-msg-body">{m.body}</div>
            </div>
          ))}
          {data?.messages?.length === 0 && <div className="lr-muted">No messages yet — generate the campaign first.</div>}
        </div>
      </div>
    </div>
  );
}
