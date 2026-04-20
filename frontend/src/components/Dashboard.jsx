import React, { useEffect, useRef, useState } from "react";

function AnimatedNumber({ value, prefix = "", suffix = "", duration = 400 }) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);

  useEffect(() => {
    const from = fromRef.current;
    const to = value;
    if (from === to) return;
    const start = performance.now();
    let raf;
    const step = (t) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      const curr = Math.round(from + (to - from) * eased);
      setDisplay(curr);
      if (p < 1) raf = requestAnimationFrame(step);
      else fromRef.current = to;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  const formatted = display.toLocaleString();
  return <span>{prefix}{formatted}{suffix}</span>;
}

function KpiCard({ label, value, prefix = "", suffix = "", sub, accent }) {
  return (
    <div className={"kpi-card" + (accent ? " accent" : "")}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        <AnimatedNumber value={value} prefix={prefix} suffix={suffix} />
      </div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

export default function Dashboard({ stats }) {
  const avgSecs = stats.avgResponseSeconds || 0;
  const avgDisplay =
    avgSecs < 60 ? `${Math.round(avgSecs)}s`
    : `${Math.floor(avgSecs / 60)}m ${Math.round(avgSecs % 60)}s`;

  return (
    <div className="dashboard">
      <KpiCard label="Leads today" value={stats.leadsProcessed} sub={`${stats.highTier} hot · ${stats.mediumTier} warm · ${stats.lowTier} cold`} />
      <KpiCard
        label="Avg response time"
        value={Math.round(avgSecs)}
        suffix="s"
        sub={<><span style={{ color: "var(--muted)" }}>Industry avg:</span> 4h 12m</>}
        accent={avgSecs > 0 && avgSecs < 120}
      />
      <KpiCard
        label="Est. pipeline"
        value={stats.pipelineValue}
        prefix="$"
        sub="this session"
        accent={stats.pipelineValue > 0}
      />
      <KpiCard label="Booked / escalated" value={stats.bookedCalls} sub="P0 handoffs to sales" />
      <KpiCard label="Messages sent" value={stats.messagesSent} sub="email + SMS auto-sent" />
      <KpiCard label="Follow-ups queued" value={stats.followupsQueued} sub="scheduled sends" />
    </div>
  );
}
