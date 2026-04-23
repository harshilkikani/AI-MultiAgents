import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// Day labels — step values map to cadence names. step=99 is the auto-reply
// fired on "yes" intent (Calendly link). step=-1 is inbound.
const STEP_LABEL = {
  "-1": "Inbound",
  0: "Day 0",
  1: "Day 3",
  2: "Day 10",
  3: "Day 24",
  99: "Auto-reply",
};

const STATUS_LABEL = {
  sent: "Delivered",
  pending: "Scheduled",
  cancelled: "Cancelled",
  failed: "Failed",
  received: "Received",
};

function fmtClock(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

function timeAgo(ts) {
  if (!ts) return "";
  const diff = Math.max(0, (Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return fmtClock(ts);
}

/**
 * iMessage-style thread view. Inbound left, outbound right.
 * Cancelled messages appear struck-through and dimmed (they're part of the
 * narrative — owner sees what WOULD have sent if the lead hadn't replied).
 */
export default function MessageThread({ campaignId, lead, onClose }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    setData(null);
    setErr(null);
    if (!lead) return;
    api.leadMessages(campaignId, lead.id).then(setData).catch((e) => setErr(e.message));
  }, [campaignId, lead?.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [data]);

  // Esc to close + body-scroll lock while the modal is open.
  useEffect(() => {
    if (!lead) return;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [lead, onClose]);

  if (!lead) return null;

  return (
    <div
      className="lr-modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Message thread for ${lead.name}`}
    >
      <div className="lr-modal lr-thread-modal" onClick={(e) => e.stopPropagation()}>
        <div className="lr-thread-head">
          <div className="lr-thread-who">
            <div className="lr-thread-avatar">
              {(lead.name || "?").split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()}
            </div>
            <div>
              <div className="lr-thread-name">{lead.name}</div>
              <div className="lr-thread-sub">
                {lead.phone || "—"} · {lead.source || "—"}
              </div>
            </div>
          </div>
          <div className="lr-thread-right">
            <span className={`lr-state-chip lr-state-${lead.state}`}>{lead.state}</span>
            <button className="lr-modal-close" onClick={onClose} aria-label="Close">✕</button>
          </div>
        </div>

        <div className="lr-thread-body">
          {err && <div className="lr-error">{err}</div>}
          {!data && !err && <div className="lr-muted lr-thread-loading">Loading thread…</div>}
          {data?.messages?.length === 0 && (
            <div className="lr-muted">No messages yet — generate the campaign first.</div>
          )}
          {data?.messages?.map((m, i) => {
            const inbound = m.direction === "in";
            const isCancelled = m.status === "cancelled";
            const isFailed = m.status === "failed";
            const label = STEP_LABEL[m.step] ?? `Step ${m.step}`;
            const when = m.sent_at
              ? fmtClock(m.sent_at)
              : m.scheduled_for
                ? `${fmtClock(m.scheduled_for)} (scheduled)`
                : "";
            const statusLabel = STATUS_LABEL[m.status] || m.status;

            return (
              <div
                key={m.id}
                className={
                  "lr-bubble-row "
                  + (inbound ? "lr-bubble-in" : "lr-bubble-out")
                  + (isCancelled ? " lr-bubble-cancelled" : "")
                  + (isFailed ? " lr-bubble-failed" : "")
                }
              >
                <div className="lr-bubble-meta">
                  <span className="lr-bubble-step">{label}</span>
                  <span className="lr-bubble-when">{when}</span>
                </div>
                <div className="lr-bubble-body">{m.body}</div>
                <div className="lr-bubble-status">
                  {inbound ? "From lead" : statusLabel}
                  {m.sent_at && <> · <span className="lr-muted">{timeAgo(m.sent_at)}</span></>}
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>

        <div className="lr-thread-foot">
          Replies from this lead land in the thread automatically when their
          phone messages your Twilio number.
        </div>
      </div>
    </div>
  );
}
