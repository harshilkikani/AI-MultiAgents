import React, { useRef, useState } from "react";
import { api } from "../api.js";
import MappingTable from "../components/MappingTable.jsx";

const VERTICALS = [
  { key: "septic",     label: "Septic",     avg: 680 },
  { key: "roofing",    label: "Roofing",    avg: 14000 },
  { key: "hvac",       label: "HVAC",       avg: 950 },
  { key: "plumbing",   label: "Plumbing",   avg: 540 },
  { key: "electrical", label: "Electrical", avg: 820 },
];

// Three-step flow:
//   step 1 "meta"    — campaign name + vertical + Calendly + pick file
//   step 2 "mapping" — review header detection, adjust, confirm + commit
//   step 3 "sample"  — generate 3 sample messages, approve → next page
export default function Upload({ onCreated }) {
  const [step, setStep] = useState("meta");
  const [name, setName] = useState("April Revival Campaign");
  const [vertical, setVertical] = useState("septic");
  const [avgTicket, setAvgTicket] = useState(680);
  const [calendlyUrl, setCalendlyUrl] = useState("");
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const [campaignId, setCampaignId] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [uploadResult, setUploadResult] = useState(null);
  const [samples, setSamples] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const setFromVertical = (v) => {
    setVertical(v);
    const m = VERTICALS.find((x) => x.key === v);
    if (m) setAvgTicket(m.avg);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  const toPreview = async (e) => {
    e?.preventDefault?.();
    if (!file) { setErr("Pick a CSV first."); return; }
    setBusy(true); setErr(null);
    try {
      const campaign = await api.createCampaign({
        name, vertical, avg_ticket: Number(avgTicket) || 0,
        calendly_url: calendlyUrl || null,
      });
      setCampaignId(campaign.id);
      const p = await api.previewLeads(campaign.id, file);
      setPreview(p);
      setMapping({}); // overrides start empty; effective = detected
      setStep("mapping");
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const refreshPreviewWithMapping = async (nextMapping) => {
    setMapping(nextMapping);
    if (!file || !campaignId) return;
    setBusy(true);
    setErr(null);
    try {
      const p = await api.previewLeads(campaignId, file, nextMapping);
      setPreview(p);
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const commitUpload = async () => {
    if (!file || !campaignId) return;
    setBusy(true); setErr(null);
    try {
      const r = await api.uploadLeads(campaignId, file, mapping);
      setUploadResult(r);
      setStep("sample");
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const regenSamples = async () => {
    if (!campaignId) return;
    setBusy(true); setErr(null);
    try {
      const r = await api.sampleGenerate(campaignId, 3);
      setSamples(r.samples || []);
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const finish = () => {
    if (campaignId) onCreated?.(campaignId);
  };

  return (
    <div className="lr-upload">
      <div className="lr-wizard-steps no-print">
        <WizardStep label="Campaign + CSV" active={step === "meta"}     done={step !== "meta"} />
        <WizardStep label="Confirm mapping" active={step === "mapping"} done={step === "sample"} />
        <WizardStep label="Preview + finish" active={step === "sample"} />
      </div>

      {step === "meta" && (
        <div className="lr-card">
          <h1>Start a revival campaign</h1>
          <p className="lr-muted">
            Upload a CSV export from your CRM. We auto-map Jobber, ServiceTitan,
            and HubSpot columns — you'll confirm the mapping on the next step
            before any data is saved.
          </p>

          <form onSubmit={toPreview} className="lr-form">
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
              <input placeholder="https://calendly.com/your-shop/30min"
                     value={calendlyUrl}
                     onChange={(e) => setCalendlyUrl(e.target.value)} />
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
                  <div className="lr-dz-sub">{(file.size / 1024).toFixed(1)} KB · ready to analyze</div>
                </div>
              ) : (
                <div>
                  <div className="lr-dz-title">Drop CSV or click to browse</div>
                  <div className="lr-dz-sub">We'll read the columns without saving anything yet.</div>
                </div>
              )}
            </div>

            <button type="submit" className="lr-btn" disabled={busy}>
              {busy ? "Reading CSV…" : "Analyze CSV →"}
            </button>
            {err && <div className="lr-error">{err}</div>}
          </form>
        </div>
      )}

      {step === "mapping" && preview && (
        <div className="lr-card">
          <h2>Confirm column mapping</h2>
          <p className="lr-muted">
            We detected these columns. Adjust anything that looks off — nothing
            is saved until you hit <strong>Confirm & upload</strong>.
          </p>

          <div className="lr-preview-stats">
            <Stat label="Rows in CSV" value={preview.total_valid + preview.total_skipped} />
            <Stat label="Would import" value={preview.total_valid} accent />
            <Stat label="Would skip" value={preview.total_skipped}
                  accent={preview.total_skipped === 0} warn={preview.total_skipped > 0} />
          </div>

          <MappingTable
            preview={preview}
            mapping={mapping}
            onChange={refreshPreviewWithMapping}
          />

          <h3>First 10 rows as we'd ingest them</h3>
          <table className="lr-table lr-preview-table">
            <thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>Source</th><th>Last contact</th></tr></thead>
            <tbody>
              {preview.preview.map((r, i) => (
                <tr key={i}>
                  <td>{r.name}</td>
                  <td className="lr-mono">{r.phone || <span className="lr-muted">—</span>}</td>
                  <td>{r.email || <span className="lr-muted">—</span>}</td>
                  <td>{r.source || <span className="lr-muted">—</span>}</td>
                  <td className="lr-mono">{r.last_contact || <span className="lr-muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {preview.skipped_reasons?.length > 0 && (
            <details className="lr-skipped">
              <summary>Why some rows would be skipped ({preview.total_skipped} total)</summary>
              <ul>{preview.skipped_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </details>
          )}

          <div className="lr-wizard-actions">
            <button className="lr-btn lr-btn-secondary" onClick={() => setStep("meta")}>← Back</button>
            <button className="lr-btn" onClick={commitUpload}
                    disabled={busy || preview.total_valid === 0}>
              {busy ? "Uploading…" : `Confirm & upload ${preview.total_valid} leads →`}
            </button>
          </div>
          {err && <div className="lr-error">{err}</div>}
        </div>
      )}

      {step === "sample" && uploadResult && (
        <div className="lr-card">
          <h2>Preview the revival messages</h2>
          <p className="lr-muted">
            Generate 3 sample messages against random leads from your list.
            Your trial allowance is not consumed — nothing is saved. If
            they sound wrong, just regenerate.
          </p>

          <div className="lr-result-stats">
            <div>
              <div className="lr-stat-label">Inserted</div>
              <div className="lr-stat-value lr-ok">{uploadResult.inserted}</div>
            </div>
            <div>
              <div className="lr-stat-label">Skipped</div>
              <div className={"lr-stat-value" + (uploadResult.skipped ? " lr-warn" : "")}>
                {uploadResult.skipped}
              </div>
            </div>
            <div>
              <div className="lr-stat-label">Campaign</div>
              <div className="lr-stat-value">#{campaignId}</div>
            </div>
          </div>

          <div className="lr-sample-actions">
            <button className="lr-btn" onClick={regenSamples} disabled={busy}>
              {busy ? "Generating…" : (samples ? "Regenerate 3 samples" : "Generate 3 samples")}
            </button>
            <button className="lr-btn lr-btn-secondary" onClick={finish}>
              Looks good — open campaign →
            </button>
          </div>

          {samples?.length > 0 && (
            <div className="lr-samples">
              {samples.map((s, i) => (
                <div key={i} className="lr-sample">
                  <div className="lr-sample-head">
                    <strong>{s.lead.name}</strong>
                    <span className="lr-muted">{s.lead.phone || "no phone"} · urgency {s.urgency_score}/10 · best: {s.best_time_of_day}</span>
                  </div>
                  <div className="lr-sample-body">
                    <div className="lr-msg lr-msg-out"><div className="lr-msg-head"><span className="lr-msg-step">Day 0</span></div><div className="lr-msg-body">{s.initial_msg}</div></div>
                    {s.drip_msgs.map((m, j) => (
                      <div key={j} className="lr-msg lr-msg-out">
                        <div className="lr-msg-head">
                          <span className="lr-msg-step">{["Day 3","Day 10","Day 24"][j]}</span>
                        </div>
                        <div className="lr-msg-body">{m}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
          {err && <div className="lr-error">{err}</div>}
        </div>
      )}
    </div>
  );
}

function WizardStep({ label, active, done }) {
  return (
    <div className={"lr-wiz-step" + (active ? " active" : "") + (done ? " done" : "")}>
      <span className="lr-wiz-dot" />
      <span>{label}</span>
    </div>
  );
}

function Stat({ label, value, accent, warn }) {
  return (
    <div className={"lr-preview-stat" + (accent ? " accent" : "") + (warn ? " warn" : "")}>
      <div className="lr-preview-stat-label">{label}</div>
      <div className="lr-preview-stat-value">{value}</div>
    </div>
  );
}
