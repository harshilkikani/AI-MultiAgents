import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { setWorkspace } from "../ws.js";

/**
 * Public /demo landing. On mount:
 *   - Stash the demo workspace id in localStorage (api.js picks it up)
 *   - Fetch /api/demo/info — if seeded, redirect to campaign detail
 *   - If not seeded, show a reset button the user can click
 */
export default function Demo({ navigate }) {
  const [status, setStatus] = useState("loading");
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    // Default to demo workspace for this page load. User can bounce back
    // to their own workspace by hitting the main nav.
    setWorkspace(2);
    (async () => {
      try {
        const i = await api.demoInfo();
        setInfo(i);
        if (i.seeded) {
          setStatus("ready");
          navigate(`/campaigns/${i.campaign_id}`);
        } else {
          setStatus("unseeded");
        }
      } catch (e) {
        setErr(e.message);
        setStatus("error");
      }
    })();
    // eslint-disable-next-line
  }, []);

  const runReset = async () => {
    setStatus("seeding");
    try {
      const r = await api.demoReset();
      navigate(`/campaigns/${r.campaign_id}`);
    } catch (e) {
      setErr(e.message);
      setStatus("error");
    }
  };

  return (
    <div className="lr-card">
      <h1>Lead Revival — live demo</h1>
      <p className="lr-muted">
        Preview customer: <strong>Hatcher Septic &amp; Drain</strong>. Read-only view of a
        real campaign mid-flight — 200 old leads, ~10 days into a 4-week drip.
      </p>
      {status === "loading" && <div className="lr-muted">Loading demo…</div>}
      {status === "seeding" && <div className="lr-muted">Rebuilding demo data (takes a few seconds)…</div>}
      {status === "unseeded" && (
        <div>
          <p className="lr-muted">Demo hasn't been seeded yet. Click below to generate 200 leads + a running campaign.</p>
          <button className="lr-btn" onClick={runReset}>Seed demo data</button>
        </div>
      )}
      {status === "ready" && <div className="lr-muted">Redirecting to the demo campaign…</div>}
      {err && <div className="lr-error">{err}</div>}
    </div>
  );
}
