import React, { useState } from "react";
import { api } from "../api.js";
import { setToken } from "../auth.js";

export default function Login({ navigate }) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await api.login(email || "demo@revival.local");
      setMode(r.mode);
      if (r.mode === "demo") {
        // DEMO: immediate stub token, route into the app.
        setToken(r.token);
        navigate("/");
      } else {
        setMsg(r.message || "Magic link sent — check your email.");
      }
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="lr-login">
      <div className="lr-card">
        <div className="lr-login-brand">
          <div className="lr-brand-mark">LR</div>
          <div>
            <div className="lr-brand-name">Lead Revival</div>
            <div className="lr-brand-sub">Wake up old leads · ship recovered revenue</div>
          </div>
        </div>
        <h1>Sign in</h1>
        <p className="lr-muted">
          Enter your email and we'll send you a one-click magic link. New here? The same link signs you up.
        </p>
        <form className="lr-form" onSubmit={submit}>
          <label className="lr-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@yourshop.com"
              required
              autoFocus
            />
          </label>
          <button className="lr-btn" type="submit" disabled={busy}>
            {busy ? "Working…" : "Send magic link"}
          </button>
          {msg && <div className="lr-login-ok">{msg}</div>}
          {err && <div className="lr-error">{err}</div>}
        </form>
        <div className="lr-login-foot">
          Or <a href="/demo" onClick={(e) => { e.preventDefault(); navigate("/demo"); }}>
            see the read-only demo workspace
          </a> first.
        </div>
      </div>
    </div>
  );
}
