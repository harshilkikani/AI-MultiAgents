import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// Common US timezones — dropdown beats a free-text box for correctness.
const COMMON_TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Phoenix",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
];

export default function Settings() {
  const [ws, setWs] = useState(null);
  const [form, setForm] = useState({
    name: "", owner_phone: "", owner_email: "", owner_timezone: "", slack_webhook_url: "",
  });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.getWorkspaceSettings()
      .then((w) => {
        setWs(w);
        setForm({
          name: w.name || "",
          owner_phone: w.owner_phone || "",
          owner_email: w.owner_email || "",
          owner_timezone: w.owner_timezone || "",
          slack_webhook_url: w.slack_webhook_url || "",
        });
      })
      .catch((e) => setErr(e.message));
  }, []);

  const set = (k) => (e) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
    setSaved(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null); setSaved(false);
    try {
      const next = await api.updateWorkspaceSettings(form);
      setWs(next);
      setSaved(true);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!ws && !err) return <div className="lr-card lr-muted">Loading…</div>;
  if (err && !ws) return <div className="lr-card lr-error">{err}</div>;

  return (
    <div className="lr-settings">
      <div className="lr-card">
        <h1>Workspace settings</h1>
        <p className="lr-muted">
          When a lead replies hot, we buzz you on the phone within 10 seconds.
          Leave any field blank to disable that channel.
        </p>

        <form className="lr-form" onSubmit={submit}>
          <label className="lr-field">
            <span>Workspace name</span>
            <input value={form.name} onChange={set("name")} required />
          </label>

          <h3>Hot-lead alerts</h3>
          <p className="lr-muted" style={{ marginTop: -4, marginBottom: 8 }}>
            Primary channel: SMS. Slack is fired in parallel if you set it.
            Alerts dedup per lead for 4 hours.
          </p>

          <label className="lr-field">
            <span>Owner phone (E.164, e.g. +12295550199)</span>
            <input
              type="tel"
              placeholder="+12295550199"
              value={form.owner_phone}
              onChange={set("owner_phone")}
              pattern="^\+[1-9]\d{7,14}$"
            />
          </label>

          <div className="lr-row">
            <label className="lr-field">
              <span>Owner email (optional — not yet used)</span>
              <input
                type="email"
                value={form.owner_email}
                onChange={set("owner_email")}
                placeholder="owner@shop.com"
              />
            </label>
            <label className="lr-field">
              <span>Owner timezone (for quiet hours)</span>
              <select value={form.owner_timezone} onChange={set("owner_timezone")}>
                <option value="">— (defaults to Eastern)</option>
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </label>
          </div>

          <label className="lr-field">
            <span>Slack incoming webhook (optional)</span>
            <input
              type="url"
              placeholder="https://hooks.slack.com/services/YOUR/WEBHOOK/PATH"
              value={form.slack_webhook_url}
              onChange={set("slack_webhook_url")}
            />
          </label>

          <button type="submit" className="lr-btn" disabled={busy}>
            {busy ? "Saving…" : "Save settings"}
          </button>
          {saved && <div className="lr-login-ok">Saved. Owner alerts are active.</div>}
          {err && <div className="lr-error">{err}</div>}
        </form>
      </div>

      <div className="lr-card">
        <h2>Integrations</h2>
        <p className="lr-muted">Direct CRM ingestion — kills the weekly CSV upload cycle.</p>
        <JobberPanel />
      </div>
    </div>
  );
}
