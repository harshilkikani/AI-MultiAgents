import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// Tiny status dot in the header. Polls /api/health every 60s. Shows green
// when the scheduler is fresh, yellow when disabled (e.g., DEMO_MODE), red
// on 503 (stale / unreachable). Hover shows details.
export default function HealthDot() {
  const [health, setHealth] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      api.healthCheck()
        .then((h) => { if (!cancelled) { setHealth(h); setErr(false); } })
        .catch(() => { if (!cancelled) { setErr(true); } });
    };
    poll();
    const iv = setInterval(poll, 60_000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  let tone = "unknown";
  let title = "Checking system health…";
  if (err) { tone = "err"; title = "Backend unreachable or scheduler stale."; }
  else if (health) {
    const s = health.scheduler || {};
    if (!s.enabled) {
      tone = "idle"; title = "Scheduler disabled (DEMO_MODE or dev).";
    } else if (s.stale) {
      tone = "err"; title = `Scheduler hasn't ticked in ${s.minutes_since_last_tick}m.`;
    } else if (s.last_tick_at) {
      tone = "ok";
      title = `Scheduler healthy · last tick ${Math.round(s.minutes_since_last_tick ?? 0)}m ago.`;
    } else {
      tone = "idle"; title = "Scheduler starting…";
    }
  }

  return (
    <span className={`lr-health-dot lr-health-${tone}`} title={title} aria-label={title}>
      <span className="lr-health-blip" />
    </span>
  );
}
