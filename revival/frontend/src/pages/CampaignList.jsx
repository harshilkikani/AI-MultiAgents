import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const fmt = (n) => "$" + Math.round(n || 0).toLocaleString();

export default function CampaignList({ onPick }) {
  const [campaigns, setCampaigns] = useState(null);
  const [statsById, setStatsById] = useState({});
  const [err, setErr] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = () => {
    let cancelled = false;
    setErr(null);
    api.listCampaigns()
      .then(async (rows) => {
        if (cancelled) return;
        setCampaigns(rows);
        const results = await Promise.allSettled(rows.map((c) => api.stats(c.id)));
        if (cancelled) return;
        const next = {};
        results.forEach((r, i) => {
          if (r.status === "fulfilled") next[rows[i].id] = r.value;
        });
        setStatsById(next);
      })
      .catch((e) => setErr(e.message));
    return () => { cancelled = true; };
  };

  useEffect(load, []);

  const togglePause = async (e, c) => {
    // Don't open the campaign when the owner clicks "Resume" inline.
    e.stopPropagation();
    setBusyId(c.id);
    try {
      if (c.paused) await api.resumeCampaign(c.id);
      else          await api.pauseCampaign(c.id);
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  };

  if (err) return <div className="lr-card lr-error">{err}</div>;
  if (!campaigns) {
    return (
      <div className="lr-campaign-list">
        {[0, 1, 2].map((i) => (
          <div key={i} className="lr-card lr-campaign-card lr-skeleton">
            <div className="lr-skel-line lr-skel-w60" />
            <div className="lr-skel-line lr-skel-w40" />
            <div className="lr-skel-line lr-skel-w80" />
          </div>
        ))}
      </div>
    );
  }
  if (campaigns.length === 0) {
    return (
      <div className="lr-card lr-empty-hero">
        <div className="lr-empty-icon">📬</div>
        <h2>No campaigns yet</h2>
        <p className="lr-muted">Upload your first CSV and we'll take it from here — four messages, four weeks, recovered revenue on the other side.</p>
        <a className="lr-btn" href="/" onClick={(e) => { e.preventDefault(); window.history.pushState({}, "", "/"); window.dispatchEvent(new PopStateEvent("popstate")); }}>
          Start your first campaign →
        </a>
      </div>
    );
  }

  return (
    <div className="lr-campaign-list">
      {campaigns.map((c) => {
        const s = statsById[c.id];
        const done = s ? s.state_counts.opted_out + s.state_counts.replied_no + s.state_counts.dead : 0;
        return (
          <div
            key={c.id}
            className={"lr-card lr-campaign-card" + (c.paused ? " paused" : "")}
            onClick={() => onPick?.(c.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter") onPick?.(c.id); }}
          >
            <div className="lr-campaign-head">
              <div>
                <div className="lr-campaign-name">
                  #{c.id} · {c.name}
                  {c.paused && <span className="lr-paused-badge">PAUSED</span>}
                  {!c.paid && <span className="lr-unpaid-badge">UNPAID</span>}
                </div>
                <div className="lr-campaign-sub">
                  {c.vertical} · avg ${Math.round(c.avg_ticket).toLocaleString()} · {c.lead_count} leads
                </div>
              </div>
              <div className="lr-campaign-actions">
                {c.paused && (
                  <button
                    className="lr-btn lr-btn-small"
                    onClick={(e) => togglePause(e, c)}
                    disabled={busyId === c.id}
                    aria-label={`Resume campaign ${c.name}`}
                  >
                    {busyId === c.id ? "…" : "Resume"}
                  </button>
                )}
                <div className="lr-campaign-net">
                  {s ? fmt(s.est_recovered_revenue) : "—"}
                  <div className="lr-campaign-net-label">recovered</div>
                </div>
              </div>
            </div>
            {s && (
              <div className="lr-campaign-states">
                <span className="lr-campaign-state" title="Haven't received Day-0 yet">
                  <b>{s.state_counts.queued}</b> queued
                </span>
                <span className="lr-campaign-state" title="Day-0 sent, drip in flight">
                  <b>{s.state_counts.contacted}</b> contacted
                </span>
                <span className="lr-campaign-state lr-hot" title="Said yes; Calendly link sent">
                  <b>{s.state_counts.replied_hot}</b> hot
                </span>
                <span className="lr-campaign-state lr-booked" title="Calendly slot confirmed">
                  <b>{s.state_counts.booked}</b> booked
                </span>
                <span className="lr-campaign-state lr-dead" title="No / stopped / no reply after Day-24">
                  <b>{done}</b> done
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
