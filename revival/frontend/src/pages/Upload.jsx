import React, { useRef, useState } from "react";
import { api } from "../api.js";

const VERTICALS = [
  { key: "septic",     label: "Septic",     avg: 680 },
  { key: "roofing",    label: "Roofing",    avg: 14000 },
  { key: "hvac",       label: "HVAC",       avg: 950 },
  { key: "plumbing",   label: "Plumbing",   avg: 540 },
  { key: "electrical", label: "Electrical", avg: 820 },
];

export default function Upload({ onCreated }) {
  const [name, setName] = useState("April Revival Campaign");
  const [vertical, setVertical] = useState("septic");
  const [avgTicket, setAvgTicket] = useState(680);
  const [calendlyUrl, setCalendlyUrl] = useState("");
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);

  const setFromVertical = (v) => {
    setVertical(v);
    const match = VERTICALS.find((x) => x.key === v);
    if (match) setAvgTicket(match.avg);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  const runUpload = async (e) => {
    e?.preventDefault?.();
    if (!file) {
      setError("Pick a CSV first.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const campaign = await api.createCampaign({
        name, vertical, avg_ticket: Number(avgTicket) || 0,
        calendly_url: calendlyUrl || null,
      });
      const up = await api.uploadLeads(campaign.id, file);
      setResult({ campaign, up });
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="lr-upload">
      <div className="lr-card">
        <h1>Start a revival campaign</h1>
        <p className="lr-muted">
          Upload a CSV export from your CRM. We handle common column names from
          Jobber, ServiceTitan, and HubSpot out of the box.
        </p>

        <form onSubmit={runUpload} className="lr-form">
          <label className="lr-field">
            <span>Campaign name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>

          <div className="lr-row">
            <label className="lr-field">
              <span>Vertical</span>
              <select value={vertical} onChange={(e) => setFromVertical(e.target.value)}>
                {VERTICALS.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}
              </select>
            </label>

            <label className="lr-field">
              <span>Avg job value ($)</span>
              <input type="number" min={0} value={avgTicket}
                     onChange={(e) => setAvgTicket(e.target.value)} />
            </label>
          </div>

          <label className="lr-field">
            <span>Calendly link (optional)</span>
            <input
              placeholder="https://calendly.com/your-shop/30min"
              value={calendlyUrl}
              onChange={(e) => setCalendlyUrl(e.target.value)}
            />
          </label>

          <div
            className={"lr-dropzone" + (dragging ? " dragging" : "") + (file ? " has-file" : "")}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file ? (
              <div>
                <div className="lr-dz-title">{file.name}</div>
                <div className="lr-dz-sub">{(file.size / 1024).toFixed(1)} KB · ready to upload</div>
              </div>
            ) : (
              <div>
                <div className="lr-dz-title">Drop CSV or click to browse</div>
                <div className="lr-dz-sub">Accepted: Jobber / ServiceTitan / HubSpot exports</div>
              </div>
            )}
          </div>

          <button type="submit" className="lr-btn" disabled={busy}>
            {busy ? "Working…" : "Create campaign + upload leads"}
          </button>

          {error && <div className="lr-error">{error}</div>}
        </form>
      </div>

      {result && (
        <div className="lr-card lr-result">
          <h2>Ingest complete</h2>
          <div className="lr-result-stats">
            <div>
              <div className="lr-stat-label">Campaign</div>
              <div className="lr-stat-value">#{result.campaign.id} · {result.campaign.name}</div>
            </div>
            <div>
              <div className="lr-stat-label">Inserted</div>
              <div className="lr-stat-value lr-ok">{result.up.inserted}</div>
            </div>
            <div>
              <div className="lr-stat-label">Skipped</div>
              <div className={"lr-stat-value" + (result.up.skipped ? " lr-warn" : "")}>{result.up.skipped}</div>
            </div>
          </div>

          {result.up.skipped_reasons?.length > 0 && (
            <details className="lr-skipped">
              <summary>Why some rows were skipped ({result.up.skipped_reasons.length} reasons)</summary>
              <ul>{result.up.skipped_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </details>
          )}

          <h3>First 5 leads</h3>
          <table className="lr-table">
            <thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>Source</th><th>State</th></tr></thead>
            <tbody>
              {result.up.preview.map((l) => (
                <tr key={l.id}>
                  <td>{l.name}</td>
                  <td>{l.phone || <span className="lr-muted">—</span>}</td>
                  <td>{l.email || <span className="lr-muted">—</span>}</td>
                  <td>{l.source || <span className="lr-muted">—</span>}</td>
                  <td><span className="lr-tag">{l.state}</span></td>
                </tr>
              ))}
            </tbody>
          </table>

          <button className="lr-btn lr-btn-secondary"
                  onClick={() => onCreated?.(result.campaign.id)}>
            Open campaign →
          </button>
        </div>
      )}
    </div>
  );
}
