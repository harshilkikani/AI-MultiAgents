import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function JobberPanel() {
  const [status, setStatus] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [syncResult, setSyncResult] = useState(null);

  const refresh = () => {
    api.jobberStatus().then(setStatus).catch((e) => setErr(e.message));
    api.listCampaigns().then((rows) => {
      setCampaigns(rows);
      if (rows[0] && !selectedCampaign) setSelectedCampaign(String(rows[0].id));
    }).catch(() => {});
  };

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  const connect = async () => {
    setBusy(true); setErr(null);
    try {
      const body = await api.jobberConnect();
      if (body.mode === "demo") {
        // Same-origin URL; hit it directly.
        await api.jobberCallback(body.authorize_url);
        refresh();
      } else {
        window.location.href = body.authorize_url;
      }
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true); setErr(null);
    try {
      await api.jobberDisconnect();
      refresh();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const sync = async () => {
    if (!selectedCampaign) { setErr("Pick a campaign to sync into."); return; }
    setBusy(true); setErr(null); setSyncResult(null);
    try {
      const r = await api.jobberSync(Number(selectedCampaign));
      setSyncResult(r);
      refresh();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!status && !err) return <div className="lr-muted">Loading…</div>;

  return (
    <div className="lr-integration">
      <div className="lr-integration-head">
        <div>
          <div className="lr-integration-title">Jobber</div>
          <div className="lr-integration-sub">
            Pull cold leads straight from your Jobber account. No more weekly CSV exports.
          </div>
        </div>
        <span className={"lr-integration-status " + (status?.connected ? "connected" : "disconnected")}>
          {status?.connected ? "Connected" : "Not connected"}
        </span>
      </div>

      {status?.connected ? (
        <div className="lr-integration-body">
          <div className="lr-integration-meta">
            {status.account_name && <span><strong>Account:</strong> {status.account_name}</span>}
            {status.last_synced_at
              ? <span><strong>Last sync:</strong> {new Date(status.last_synced_at).toLocaleString()}</span>
              : <span className="lr-muted">Never synced</span>}
            {status.last_sync_stats && (
              <span className="lr-muted">
                {status.last_sync_stats.inserted} new · {status.last_sync_stats.already_present} already present · {status.last_sync_stats.skipped} skipped
              </span>
            )}
          </div>

          <div className="lr-form" style={{ marginTop: 10 }}>
            <label className="lr-field">
              <span>Sync into campaign</span>
              <select value={selectedCampaign} onChange={(e) => setSelectedCampaign(e.target.value)}>
                <option value="">— pick a campaign —</option>
                {campaigns.map((c) => (
                  <option key={c.id} value={c.id}>#{c.id} · {c.name} ({c.vertical})</option>
                ))}
              </select>
            </label>
            <div className="lr-sample-actions">
              <button className="lr-btn" onClick={sync} disabled={busy}>
                {busy ? "Syncing…" : "Sync now"}
              </button>
              <button className="lr-btn lr-btn-secondary" onClick={disconnect} disabled={busy}>
                Disconnect
              </button>
            </div>
          </div>

          {syncResult && (
            <div className="lr-login-ok">
              Synced {syncResult.pulled} rows · {syncResult.inserted} new · {syncResult.already_present} already present · {syncResult.skipped} skipped.
            </div>
          )}
        </div>
      ) : (
        <div className="lr-integration-body">
          <p className="lr-muted">
            Clicking below opens Jobber's consent screen. We only ask for read
            access to clients, requests, and jobs — no write permissions.
          </p>
          <button className="lr-btn" onClick={connect} disabled={busy}>
            {busy ? "Opening Jobber…" : "Connect Jobber"}
          </button>
        </div>
      )}

      {err && <div className="lr-error">{err}</div>}
    </div>
  );
}
