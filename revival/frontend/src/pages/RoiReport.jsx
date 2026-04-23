import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const fmt = (n) => "$" + Math.round(n || 0).toLocaleString();

export default function RoiReport({ id, onBack }) {
  const [campaign, setCampaign] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.getCampaign(id).then(setCampaign);
    api.stats(id).then(setStats);
  }, [id]);

  if (!campaign || !stats) {
    return (
      <div className="lr-report">
        <div className="lr-card lr-skeleton">
          <div className="lr-skel-line lr-skel-w80" />
          <div className="lr-skel-line lr-skel-w60" />
          <div className="lr-skel-line lr-skel-w40" />
        </div>
      </div>
    );
  }

  return (
    <div className="lr-report">
      <div className="lr-report-toolbar no-print">
        <button className="lr-btn lr-btn-secondary" onClick={onBack}>← Back</button>
        <button className="lr-btn" onClick={() => window.print()}>Print / Save PDF</button>
      </div>

      <div className="lr-report-page">
        <header className="lr-report-header">
          <div>
            <div className="lr-report-eyebrow">Lead Revival — Campaign Report</div>
            <h1 className="lr-report-title">{campaign.name}</h1>
            <div className="lr-report-sub">
              {campaign.vertical} · Avg ticket ${Math.round(campaign.avg_ticket).toLocaleString()} · {stats.total_leads} leads touched
            </div>
          </div>
          <div className="lr-report-date">
            {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
          </div>
        </header>

        <section className="lr-report-headline">
          <div className="lr-report-headline-label">Revenue recovered</div>
          <div className="lr-report-headline-value">{fmt(stats.est_recovered_revenue)}</div>
          <div className="lr-report-headline-net">
            Net vs. {fmt(stats.keres_cost)} campaign fee: <strong>{stats.net >= 0 ? "+" : ""}{fmt(stats.net)}</strong>
          </div>
        </section>

        <section>
          <h2>The math</h2>
          <table className="lr-report-table">
            <tbody>
              <tr><td>Leads in campaign</td><td className="lr-right">{stats.total_leads}</td></tr>
              <tr><td>Contacted (received ≥ 1 msg)</td>
                  <td className="lr-right">{stats.state_counts.contacted + stats.state_counts.replied_hot + stats.state_counts.replied_no + stats.state_counts.booked + stats.state_counts.opted_out}</td></tr>
              <tr><td>Inbound replies</td><td className="lr-right">{stats.inbound_count}</td></tr>
              <tr className="lr-report-divider"><td>Hot leads (yes / interested)</td><td className="lr-right">{stats.hot_count}</td></tr>
              <tr><td>Booked (Calendly confirmed)</td><td className="lr-right">{stats.booked_count}</td></tr>
              <tr className="lr-report-divider"><td>Avg job value</td><td className="lr-right">{fmt(stats.avg_ticket)}</td></tr>
              <tr><td>Recovered revenue = booked × avg ticket</td><td className="lr-right">{fmt(stats.est_recovered_revenue)}</td></tr>
              <tr><td>Pipeline (hot × avg × 50% conversion)</td><td className="lr-right">{fmt(stats.est_pipeline_revenue - stats.est_recovered_revenue)}</td></tr>
              <tr className="lr-report-divider"><td>Lead Revival campaign fee</td><td className="lr-right">–{fmt(stats.keres_cost)}</td></tr>
              <tr><td><strong>Net</strong></td><td className="lr-right"><strong>{stats.net >= 0 ? "+" : ""}{fmt(stats.net)}</strong></td></tr>
            </tbody>
          </table>
        </section>

        <section>
          <h2>Lead state breakdown</h2>
          <div className="lr-report-states">
            {Object.entries(stats.state_counts).map(([k, v]) => (
              <div key={k} className="lr-report-state">
                <div className="lr-report-state-label">{k.replaceAll("_", " ")}</div>
                <div className="lr-report-state-value">{v}</div>
              </div>
            ))}
          </div>
        </section>

        <footer className="lr-report-footer">
          Report generated from your live campaign data. Methodology: booked = Calendly-confirmed;
          hot = reply classified as affirmative; pipeline = hot × avg ticket × 50% conversion factor.
          Close rate, avg ticket, and pipeline conversion factor are configurable per workspace.
        </footer>
      </div>
    </div>
  );
}
