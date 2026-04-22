import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const fmt = (n) => "$" + Math.round(n || 0).toLocaleString();

export default function CampaignList({ onPick }) {
  const [campaigns, setCampaigns] = useState(null);
  const [statsById, setStatsById] = useState({});
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.listCampaigns()
      .then(async (rows) => {
        if (cancelled) return;
        setCampaigns(rows);
        // Fetch stats in parallel.
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
  }, []);

  if (err) return <div className="lr-card lr-error">{err}</div>;
  if (!campaigns) return <div className="lr-card lr-muted">Loading…</div>;
  if (campaigns.length === 0) {
    return (
      <div className="lr-card">
        <h2>No campaigns yet</h2>
        <p className="lr-muted">Head to Upload to kick off your first revival.</p>
      </div>
    );
  }

  return (
    <div className="lr-campaign-list">
      {campaigns.map((c) => {
        const s = statsById[c.id];
        return (
          <div key={c.id} className="lr-card lr-campaign-card" onClick={() => onPick?.(c.id)}>
            <div className="lr-campaign-head">
              <div>
                <div className="lr-campaign-name">
                  #{c.id} · {c.name}
                  {c.paused && <span className="lr-paused-badge">PAUSED</span>}
                </div>
                <div className="lr-campaign-sub">
                  {c.vertical} · avg ${Math.round(c.avg_ticket).toLocaleString()} · {c.lead_count} leads
                  {c.paid ? " · paid" : " · unpaid"}
                </div>
              </div>
              <div className="lr-campaign-net">
                {s ? fmt(s.est_recovered_revenue) : "—"}
                <div className="lr-campaign-net-label">recovered</div>
              </div>
            </div>
            {s && (
              <div className="lr-campaign-states">
                <span className="lr-campaign-state"><b>{s.state_counts.queued}</b> queued</span>
                <span className="lr-campaign-state"><b>{s.state_counts.contacted}</b> contacted</span>
                <span className="lr-campaign-state lr-hot"><b>{s.state_counts.replied_hot}</b> hot</span>
                <span className="lr-campaign-state lr-booked"><b>{s.state_counts.booked}</b> booked</span>
                <span className="lr-campaign-state lr-dead"><b>{s.state_counts.opted_out + s.state_counts.replied_no + s.state_counts.dead}</b> done</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
