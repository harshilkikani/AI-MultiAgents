import React, { useState } from "react";

export default function AgentCard({ step, name, running, status, rawJson, children }) {
  const [showJson, setShowJson] = useState(false);
  const pillClass = status === "error" ? "pill err" : status === "ok" ? "pill ok" : "pill";
  const cardClass =
    "agent-card" +
    (status === "error" ? " err" : "") +
    (!status && !running ? " idle" : "");

  return (
    <div className={cardClass}>
      <div className="agent-head">
        <div className="agent-title">
          <span className="agent-badge">Step {step}</span>
          <span>{name}</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {rawJson && !running && status === "ok" && (
            <button
              type="button"
              className="json-toggle"
              onClick={() => setShowJson((v) => !v)}
            >
              {showJson ? "hide JSON" : "view JSON"}
            </button>
          )}
          {running ? (
            <span className="pill running">
              <span className="spinner" />
              <span>running</span>
            </span>
          ) : status ? (
            <span className={pillClass}>{status === "ok" ? "done" : "error"}</span>
          ) : (
            <span className="pill">idle</span>
          )}
        </div>
      </div>
      {showJson && rawJson ? (
        <pre className="json-dump">{JSON.stringify(rawJson, null, 2)}</pre>
      ) : (
        children
      )}
    </div>
  );
}
