import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import LeadTable from "../components/LeadTable.jsx";
import MessageThread from "../components/MessageThread.jsx";
import StateCounts from "../components/StateCounts.jsx";

export default function CampaignDetail({ id, onOpenReport }) {
  const [campaign, setCampaign] = useState(null);
  const [stats, setStats] = useState(null);
  const [leads, setLeads] = useState([]);
  const [filter, setFilter] = useState(null);
  const [openLead, setOpenLead] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const refresh = async () => {
    setErr(null);
    try {
      const [c, s, l] = await Promise.all([
        api.getCampaign(id),
        api.stats(id),
        api.listLeads(id, filter || undefined),
      ]);
      setCampaign(c);
      setStats(s);
      setLeads(l);
    } catch (e) {
      setErr(e.message);
    }
  };

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [id, filter]);

  const runGenerate = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.generate(id);
      await refresh();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const togglePause = async () => {
    if (!campaign) return;
    setBusy(true); setErr(null);
    try {
      if (campaign.paused) await api.resumeCampaign(id);
      else                 await api.pauseCampaign(id);
      await refresh();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (err) return <div className="lr-card lr-error">{err}</div>;
  if (!campaign) return <div className="lr-card lr-muted">Loading…</div>;

  return (
    <div className="lr-detail">
      {campaign.paused && (
        <div className="lr-pause-banner">
          <div>
            <strong>Campaign paused.</strong> Scheduled sends are on hold; manual sends are blocked.
            {campaign.paused_at && (
              <span className="lr-muted"> Since {new Date(campaign.paused_at).toLocaleString()}.</span>
            )}
          </div>
          <button className="lr-btn lr-btn-small" onClick={togglePause} disabled={busy}>
            {busy ? "Resuming…" : "Resume"}
          </button>
        </div>
      )}

      <div className="lr-card">
        <div className="lr-detail-head">
          <div>
            <h1>#{campaign.id} · {campaign.name}
              {campaign.paused && <span className="lr-paused-badge">PAUSED</span>}
            </h1>
            <div className="lr-muted">
              {campaign.vertical} · avg ${Math.round(campaign.avg_ticket).toLocaleString()} ·
              {campaign.calendly_url ? <> Calendly connected</> : <> no Calendly link set</>}
            </div>
          </div>
          <div className="lr-detail-actions">
            <button
              className={"lr-btn lr-btn-secondary" + (campaign.paused ? " lr-btn-warn" : "")}
              onClick={togglePause}
              disabled={busy}
            >
              {campaign.paused ? "Resume campaign" : "Pause campaign"}
            </button>
            <button className="lr-btn lr-btn-secondary" onClick={runGenerate} disabled={busy}>
              {busy ? "Generating…" : "Regenerate messages"}
            </button>
            <button className="lr-btn" onClick={() => onOpenReport?.(id)}>
              Open ROI report →
            </button>
          </div>
        </div>

        {stats && (
          <>
            <StateCounts counts={stats.state_counts} onPick={setFilter} selected={filter} />

            <div className="lr-kpi-row">
              <Kpi label="Recovered revenue" value={`$${Math.round(stats.est_recovered_revenue).toLocaleString()}`} accent />
              <Kpi label="Pipeline (hot)" value={`$${Math.round(stats.est_pipeline_revenue).toLocaleString()}`} />
              <Kpi label="Messages sent" value={stats.messages_sent} />
              <Kpi label="Pending" value={stats.messages_pending} />
              <Kpi label="Inbound replies" value={stats.inbound_count} />
              <Kpi label="Net vs. $1,500 fee" value={`${stats.net >= 0 ? "+" : ""}$${Math.round(stats.net).toLocaleString()}`}
                   accent={stats.net >= 0} />
            </div>
          </>
        )}
      </div>

      <div className="lr-card">
        <div className="lr-card-head">
          <h2>Leads{filter ? ` · ${filter}` : ""}</h2>
          <span className="lr-muted">{leads.length} shown</span>
        </div>
        <LeadTable leads={leads} onPick={setOpenLead} />
      </div>

      <MessageThread campaignId={id} lead={openLead} onClose={() => setOpenLead(null)} />
    </div>
  );
}

function Kpi({ label, value, accent }) {
  return (
    <div className={"lr-kpi" + (accent ? " lr-kpi-accent" : "")}>
      <div className="lr-kpi-label">{label}</div>
      <div className="lr-kpi-value">{value}</div>
    </div>
  );
}
