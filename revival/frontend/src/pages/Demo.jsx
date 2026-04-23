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
    <div className="lr-card lr-demo-card">
      <div className="lr-demo-hero">
        <div className="lr-brand-mark lr-demo-mark">LR</div>
        <div>
          <h1>Live demo workspace</h1>
          <p className="lr-muted" style={{ marginBottom: 0 }}>
            Preview customer: <strong>Hatcher Septic &amp; Drain</strong>. 200 old leads,
            ~10 days into a 4-week drip. All data is fake; nothing is sent.
          </p>
        </div>
      </div>

      {status === "loading" && (
        <div className="lr-skeleton">
          <div className="lr-skel-line lr-skel-w60" />
          <div className="lr-skel-line lr-skel-w80" />
          <div className="lr-skel-line lr-skel-w40" />
        </div>
      )}
      {status === "seeding" && (
        <div className="lr-demo-progress">
          <div className="lr-demo-spin" aria-hidden="true" />
          Building demo data — seeding leads, generating messages, simulating ~10 days of drip.
        </div>
      )}
      {status === "unseeded" && (
        <div>
          <p className="lr-muted">Demo hasn't been seeded yet. One click generates 200 leads + a running campaign with realistic replies and bookings.</p>
          <div style={{ display: "flex", gap: 10, marginTop: 6 }}>
            <button className="lr-btn" onClick={runReset}>Seed demo data</button>
            <button className="lr-btn lr-btn-secondary" onClick={() => { setWorkspace(1); navigate("/"); }}>
              Or head to your workspace →
            </button>
          </div>
        </div>
      )}
      {status === "ready" && <div className="lr-muted">Redirecting to the demo campaign…</div>}
      {err && (
        <div className="lr-error" style={{ marginTop: 14 }}>
          {err}
          {info && info.seeded === false && (
            <> · <button className="lr-btn lr-btn-small" onClick={runReset} style={{ marginLeft: 8 }}>Retry seed</button></>
          )}
        </div>
      )}
    </div>
  );
}
