import React from "react";
import AgentCard from "./AgentCard.jsx";

const ACTION_LABELS = {
  book_call: "Book a call",
  send_pricing: "Send pricing",
  escalate_to_sales: "Escalate to sales",
  nurture_later: "Nurture later",
  do_not_prioritize: "Do not prioritize",
};

function statusFor(logs, name) {
  if (!logs) return null;
  const row = logs.find((l) => l.agent === name);
  return row ? row.status : null;
}

function Arrow() {
  return <div className="flow-arrow">↓</div>;
}

export default function Results({ result, loading, error, revealedStage = 6, activeLead }) {
  if (error) {
    return (
      <div className="card">
        <h2>Live Pipeline</h2>
        <div className="error">Something went wrong: {error}</div>
      </div>
    );
  }

  if (!result && !loading) {
    return (
      <div className="card">
        <h2>Live Pipeline</h2>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          Click <strong>Start Demo</strong> to stream leads through the agents, or pick any lead from the Inbox.
        </p>
      </div>
    );
  }

  const r = result || {};
  const logs = r.logs || [];
  const isRunning = (stageIdx) => loading && revealedStage === stageIdx - 1;

  const activeHeader = activeLead && (
    <div className="active-lead-banner">
      <div>
        <div className="active-lead-name">
          {activeLead.contact_name || "Anonymous"}
          <span className="muted"> · {activeLead.source}</span>
        </div>
        <div className="active-lead-msg">"{activeLead.message}"</div>
      </div>
    </div>
  );

  return (
    <div className="pipeline">
      {activeHeader}
      <AgentCard step={1} name="Intake Agent" running={isRunning(0)}
                 status={statusFor(logs, "Intake Agent")}
                 rawJson={r.intake}>
        {r.intake && (
          <dl className="kv">
            <dt>Name</dt><dd>{r.intake.name || "—"}</dd>
            <dt>Business</dt><dd>{r.intake.business_type || "—"}</dd>
            <dt>Service</dt><dd>{r.intake.service_requested || "—"}</dd>
            <dt>Urgency</dt><dd>{r.intake.urgency || "—"}</dd>
            <dt>Budget</dt><dd>{r.intake.budget || "—"}</dd>
            <dt>Key needs</dt>
            <dd>
              <div className="chips">
                {(r.intake.key_needs || []).map((n, i) => <span key={i} className="chip">{n}</span>)}
                {(!r.intake.key_needs || r.intake.key_needs.length === 0) && <span style={{ color: "var(--muted)" }}>—</span>}
              </div>
            </dd>
            <dt>Summary</dt><dd>{r.intake.clean_summary}</dd>
          </dl>
        )}
      </AgentCard>

      <Arrow />

      <AgentCard step={2} name="Qualification Agent"
                 running={isRunning(1)}
                 status={statusFor(logs, "Qualification Agent")}
                 rawJson={r.qualification}>
        {r.qualification && (() => {
          const pos = r.qualification.positive_signals || [];
          const neg = r.qualification.red_flags || [];
          return (
            <>
              <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 10 }}>
                <span className={`pill ${r.qualification.tier.toLowerCase()}`}>{r.qualification.tier} tier</span>
                <span className="pill">intent {r.qualification.intent_score}/100</span>
              </div>
              <dl className="kv">
                <dt>Positive signals</dt>
                <dd>
                  <div className="chips">
                    {pos.map((n, i) => <span key={i} className="chip good">{n}</span>)}
                    {pos.length === 0 && <span style={{ color: "var(--muted)" }}>—</span>}
                  </div>
                </dd>
                <dt>Red flags</dt>
                <dd>
                  <div className="chips">
                    {neg.map((n, i) => <span key={i} className="chip bad">{n}</span>)}
                    {neg.length === 0 && <span style={{ color: "var(--muted)" }}>—</span>}
                  </div>
                </dd>
                <dt>Reasoning</dt><dd>{r.qualification.reasoning}</dd>
              </dl>
            </>
          );
        })()}
      </AgentCard>

      <Arrow />

      <AgentCard step={3} name="Response Agent"
                 running={isRunning(2)}
                 status={statusFor(logs, "Response Agent")}
                 rawJson={r.response}>
        {r.response && (
          <>
            <div style={{ marginBottom: 8 }}>
              <span className="pill">tone: {r.response.tone}</span>
            </div>
            <div className="msg-box">{r.response.message}</div>
            <div style={{ marginTop: 10, fontSize: 13, color: "var(--muted)" }}>
              CTA → <span style={{ color: "var(--text)" }}>{r.response.cta}</span>
            </div>
          </>
        )}
      </AgentCard>

      <Arrow />

      <AgentCard step={4} name="Follow-Up Agent"
                 running={isRunning(3)}
                 status={statusFor(logs, "Follow-Up Agent")}
                 rawJson={r.follow_up}>
        {r.follow_up && (() => {
          const msgs = r.follow_up.messages || [];
          return (
            <>
              <div style={{ marginBottom: 10 }}>
                <span className="pill">
                  {r.follow_up.follow_up_needed ? "follow-up on" : "no follow-up"}
                </span>
              </div>
              <div style={{ fontSize: 14, marginBottom: 10 }}>{r.follow_up.strategy}</div>
              <div className="followups">
                {msgs.map((m, i) => (
                  <div className="followup" key={i}>
                    <div className="head"><span>{m.when}</span>·<span>{m.channel}</span></div>
                    <div>{m.message}</div>
                  </div>
                ))}
                {msgs.length === 0 && (
                  <div style={{ color: "var(--muted)", fontSize: 13 }}>No follow-up messages scheduled.</div>
                )}
              </div>
            </>
          );
        })()}
      </AgentCard>

      <Arrow />

      <AgentCard step={5} name="Action Agent"
                 running={isRunning(4)}
                 status={statusFor(logs, "Action Agent")}
                 rawJson={r.action}>
        {r.action && (
          <>
            <div className="priority-row">
              <div className="action">{ACTION_LABELS[r.action.next_action] || r.action.next_action}</div>
              <span className="priority">{r.action.priority}</span>
              {r.action.estimated_pipeline_value_usd > 0 && (
                <span className="pill" style={{ color: "var(--ok)" }}>
                  ~${r.action.estimated_pipeline_value_usd.toLocaleString()} pipeline
                </span>
              )}
            </div>
            <div style={{ fontSize: 14, color: "var(--text)" }}>{r.action.justification}</div>
          </>
        )}
      </AgentCard>

      {r.manager_summary && (
        <div className="final">
          <h2>Manager · Final Decision</h2>
          <div className="priority-row">
            <div className="action">{ACTION_LABELS[r.action?.next_action] || "—"}</div>
            {r.action && <span className="priority">{r.action.priority}</span>}
            {r.qualification && (
              <span className={`pill ${r.qualification.tier.toLowerCase()}`}>
                {r.qualification.tier} tier
              </span>
            )}
          </div>
          <div style={{ fontSize: 15, lineHeight: 1.55 }}>{r.manager_summary}</div>

          <div className="logs">
            <h3>Agent Run Log</h3>
            {logs.map((l, i) => (
              <div className="log-row" key={i}>
                <span>{l.agent}</span>
                <span>
                  <span className={`pill ${l.status === "ok" ? "ok" : "err"}`}>{l.status}</span>
                  <span style={{ marginLeft: 8 }}>{l.duration_ms} ms</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
