import React, { useEffect, useMemo, useRef, useState } from "react";
import Inbox from "./components/Inbox.jsx";
import Dashboard from "./components/Dashboard.jsx";
import ActivityFeed from "./components/ActivityFeed.jsx";
import Results from "./components/Results.jsx";
import LeadForm from "./components/LeadForm.jsx";
import DemoVideos from "./components/DemoVideos.jsx";
import CallSimulator from "./components/CallSimulator.jsx";
import Integrations from "./components/Integrations.jsx";
import RoiCalculator from "./components/RoiCalculator.jsx";
import PortalPreview from "./components/PortalPreview.jsx";
import { processLead, fetchSampleLeads } from "./api";

const STAGES = ["intake", "qualification", "response", "follow_up", "action", "manager_summary"];
const SPEED_MAP = { "1x": 1, "2x": 2, "5x": 5 };

// Vertical-specific config drives copy and the revenue benchmarks used when
// the activity feed logs booked calls / escalations.
const VERTICALS = {
  septic: {
    label: "Septic",
    tagline: "24/7 emergency pumping, routine service, new installs.",
    emoji: "🚰",
    accent: "#b08b5e",
  },
  roofing: {
    label: "Roofing",
    tagline: "Storm-damage triage, inspections, commercial bids.",
    emoji: "🏠",
    accent: "#d4a574",
  },
  hvac: {
    label: "HVAC",
    tagline: "After-hours repairs, maintenance plans, peak-season dispatch.",
    emoji: "❄️",
    accent: "#87b5e8",
  },
};

let idCounter = 1;
const nextId = () => `id-${idCounter++}`;

function useRoute() {
  const getPath = () =>
    (typeof window !== "undefined" ? window.location.pathname : "/") || "/";
  const [path, setPath] = useState(getPath);
  useEffect(() => {
    const onPop = () => setPath(getPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const navigate = (to) => {
    if (typeof window === "undefined") return;
    window.history.pushState({}, "", to);
    setPath(to);
  };
  return [path, navigate];
}

export default function App() {
  const [path, navigate] = useRoute();

  // Streaming inbox
  const [leadPool, setLeadPool] = useState([]);
  const [inbox, setInbox] = useState([]);
  const [activeLead, setActiveLead] = useState(null);
  const [result, setResult] = useState(null);
  const [revealedStage, setRevealedStage] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Dashboard stats
  const [stats, setStats] = useState({
    leadsProcessed: 0,
    highTier: 0,
    mediumTier: 0,
    lowTier: 0,
    pipelineValue: 0,
    bookedCalls: 0,
    messagesSent: 0,
    followupsQueued: 0,
    avgResponseSeconds: 0,
    _responseTimes: [],
  });

  // Activity feed
  const [activity, setActivity] = useState([]);

  // Clock for "time ago" re-renders
  const [now, setNow] = useState(Date.now());

  // Demo controls
  const [demoRunning, setDemoRunning] = useState(false);
  const [speed, setSpeed] = useState("2x");
  const [showManual, setShowManual] = useState(false);
  const [showCallSim, setShowCallSim] = useState(false);
  const [vertical, setVertical] = useState(null); // null until prospect picks
  const streamTimerRef = useRef(null);
  const clockRef = useRef(null);
  const queuedRef = useRef([]);

  // Load the lead pool on mount
  useEffect(() => {
    fetchSampleLeads().then((pool) => setLeadPool(pool || []));
  }, []);

  // Tick a clock every second so timestamps in the inbox update
  useEffect(() => {
    clockRef.current = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(clockRef.current);
  }, []);

  const pushActivity = (kind, title, detail) => {
    setActivity((prev) => [
      { id: nextId(), kind, title, detail, ts: Date.now() },
      ...prev,
    ].slice(0, 40));
  };

  const simulateSends = (lead, data) => {
    const recipient = lead.contact_email || "(no email on file)";
    const name = lead.contact_name || "lead";

    // 1. Response Agent → simulated email send
    pushActivity(
      "email_sent",
      `Email sent to ${name}`,
      `${recipient} · ${data.response.tone} tone · ${data.response.cta}`
    );

    // 2. Follow-up scheduled
    if (data.follow_up.follow_up_needed) {
      (data.follow_up.messages || []).forEach((m) => {
        const kind = m.channel === "sms" ? "sms_queued" : "email_sent";
        pushActivity(
          kind,
          `${m.channel.toUpperCase()} scheduled · ${m.when}`,
          `to ${name} — "${m.message.slice(0, 60)}${m.message.length > 60 ? "..." : ""}"`
        );
      });
    } else {
      pushActivity("nurture", `Added to nurture list`, `${name} — no active follow-up`);
    }

    // 3. Action agent outcome
    const action = data.action.next_action;
    if (action === "escalate_to_sales") {
      pushActivity("slack_ping", `🔥 Sales notified in #sales-hot`, `${name} flagged P0 · est. $${data.action.estimated_pipeline_value_usd.toLocaleString()} pipeline`);
      pushActivity("crm_task", `HubSpot task created`, `Call ${name} today — ${data.action.priority}`);
    } else if (action === "book_call") {
      pushActivity("calendly", `Calendly link sent`, `${name} routed to AE calendar`);
    } else if (action === "send_pricing") {
      pushActivity("crm_task", `Pricing one-pager queued`, `${recipient} · ${data.action.priority}`);
    } else if (action === "nurture_later") {
      pushActivity("nurture", `Added to long-cycle nurture`, `${name} — revisit in 30 days`);
    }
  };

  const revealProgressively = (lead, data) => {
    setResult({});
    let i = 0;
    const stageInterval = 450 / SPEED_MAP[speed];
    const tick = () => {
      if (i >= STAGES.length) {
        setResult(data);
        setLoading(false);

        // Update stats after full reveal
        const tier = data.qualification.tier;
        const value = data.action.estimated_pipeline_value_usd || 0;
        const fuCount = (data.follow_up.messages || []).length;
        const booked = data.action.next_action === "escalate_to_sales" || data.action.next_action === "book_call";
        const responseTimeSec = 20 + Math.random() * 40; // 20-60s, always beats the 4h12m benchmark

        setStats((s) => {
          const rt = [...s._responseTimes, responseTimeSec];
          return {
            leadsProcessed: s.leadsProcessed + 1,
            highTier: s.highTier + (tier === "High" ? 1 : 0),
            mediumTier: s.mediumTier + (tier === "Medium" ? 1 : 0),
            lowTier: s.lowTier + (tier === "Low" ? 1 : 0),
            pipelineValue: s.pipelineValue + value,
            bookedCalls: s.bookedCalls + (booked ? 1 : 0),
            messagesSent: s.messagesSent + 1,
            followupsQueued: s.followupsQueued + fuCount,
            _responseTimes: rt,
            avgResponseSeconds: rt.reduce((a, b) => a + b, 0) / rt.length,
          };
        });

        // Mark processed in inbox
        setInbox((prev) => prev.map((l) =>
          l.id === lead.id
            ? { ...l, processed: true, processing: false, tier }
            : l
        ));

        // Fire simulated sends
        simulateSends(lead, data);
        return;
      }
      const partial = {};
      for (let j = 0; j <= i; j++) partial[STAGES[j]] = data[STAGES[j]];
      partial.lead_input = data.lead_input;
      partial.logs = (data.logs || []).slice(0, i + 1);
      setResult(partial);
      setRevealedStage(i);
      i += 1;
      setTimeout(tick, stageInterval);
    };
    tick();
  };

  const runLead = async (lead) => {
    setActiveLead(lead);
    setLoading(true);
    setError(null);
    setResult(null);
    setRevealedStage(-1);

    setInbox((prev) => prev.map((l) =>
      l.id === lead.id ? { ...l, processing: true } : l
    ));

    const payload = {
      message: lead.message,
      source: lead.source,
      budget: lead.budget,
      service_requested: lead.service_requested,
      urgency: lead.urgency,
      contact_name: lead.contact_name,
      contact_email: lead.contact_email,
    };

    try {
      const data = await processLead(payload);
      revealProgressively(lead, data);
    } catch (e) {
      setError(e.message || String(e));
      setLoading(false);
      setInbox((prev) => prev.map((l) =>
        l.id === lead.id ? { ...l, processing: false } : l
      ));
    }
  };

  // Filter pool to the currently-selected vertical (fallback: all leads).
  const verticalPool = useMemo(() => {
    if (!vertical) return leadPool;
    return leadPool.filter((l) => l.vertical === vertical);
  }, [leadPool, vertical]);

  // --- Demo streaming ---
  const startDemo = () => {
    if (verticalPool.length === 0) return;
    setDemoRunning(true);
    queuedRef.current = [...verticalPool].sort(() => Math.random() - 0.5);
    // drop the first lead in right away
    ingestNext();
    scheduleNext();
  };

  const ingestNext = () => {
    const next = queuedRef.current.shift();
    if (!next) {
      setDemoRunning(false);
      return;
    }
    const lead = { ...next, id: nextId(), arrivedAt: Date.now(), processed: false };
    setInbox((prev) => [lead, ...prev]);
    // auto-process if nothing else is active
    setTimeout(() => {
      setInbox((prev) => {
        const unprocessed = prev.find((l) => !l.processed && !l.processing);
        if (unprocessed) runLead(unprocessed);
        return prev;
      });
    }, 300);
  };

  const scheduleNext = () => {
    if (streamTimerRef.current) clearTimeout(streamTimerRef.current);
    const baseDelay = 4500; // 4.5s between arrivals at 1x
    const delay = baseDelay / SPEED_MAP[speed] + Math.random() * 2000 / SPEED_MAP[speed];
    streamTimerRef.current = setTimeout(() => {
      if (queuedRef.current.length === 0) {
        setDemoRunning(false);
        return;
      }
      ingestNext();
      scheduleNext();
    }, delay);
  };

  const stopDemo = () => {
    if (streamTimerRef.current) clearTimeout(streamTimerRef.current);
    setDemoRunning(false);
  };

  const resetDemo = () => {
    stopDemo();
    setInbox([]);
    setResult(null);
    setActiveLead(null);
    setActivity([]);
    setStats({
      leadsProcessed: 0, highTier: 0, mediumTier: 0, lowTier: 0,
      pipelineValue: 0, bookedCalls: 0, messagesSent: 0, followupsQueued: 0,
      avgResponseSeconds: 0, _responseTimes: [],
    });
  };

  const chooseVertical = (v) => {
    if (v === vertical) return;
    resetDemo();
    setVertical(v);
  };

  const handleManualRun = async (payload) => {
    const lead = {
      ...payload,
      id: nextId(),
      arrivedAt: Date.now(),
      processed: false,
      contact_name: payload.contact_name || "Manual entry",
      contact_email: payload.contact_email || "manual@input.local",
    };
    setInbox((prev) => [lead, ...prev]);
    setShowManual(false);
    setTimeout(() => runLead(lead), 100);
  };

  if (path.replace(/\/$/, "") === "/portal-preview") {
    return <PortalPreview onExit={() => navigate("/")} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <img src="/KeresLogo.png" alt="Keres" className="brand-logo" />
          <div className="brand-text">
            <h1>Keres</h1>
            <p>AI lead automation for septic, roofing & HVAC. Qualify, reply to, and route every inbound lead in under 60 seconds.</p>
          </div>
        </div>
        {vertical && (
          <div className="controls">
            <div className="speed-group">
              {Object.keys(SPEED_MAP).map((s) => (
                <button
                  key={s}
                  className={"speed-btn" + (speed === s ? " active" : "")}
                  onClick={() => setSpeed(s)}
                >{s}</button>
              ))}
            </div>
            {demoRunning ? (
              <button className="btn secondary" onClick={stopDemo}>Pause Demo</button>
            ) : (
              <button className="btn" onClick={startDemo} disabled={verticalPool.length === 0}>
                ▶ Start Demo
              </button>
            )}
            <button className="btn ghost" onClick={resetDemo}>Reset</button>
            <button className="btn ghost" onClick={() => setShowManual((v) => !v)}>
              {showManual ? "Close" : "+ Manual lead"}
            </button>
          </div>
        )}
      </header>

      <div className="vertical-picker" role="tablist" aria-label="Choose your industry">
        <div className="vertical-picker-label">
          {vertical ? "Industry" : "Select your industry to start →"}
        </div>
        <div className="vertical-picker-tabs">
          {Object.entries(VERTICALS).map(([key, v]) => (
            <button
              key={key}
              role="tab"
              aria-selected={vertical === key}
              className={"vertical-tab" + (vertical === key ? " active" : "")}
              onClick={() => chooseVertical(key)}
              style={vertical === key ? { borderColor: v.accent } : undefined}
            >
              <span className="vertical-tab-emoji" aria-hidden="true">{v.emoji}</span>
              <span className="vertical-tab-text">
                <span className="vertical-tab-label">{v.label}</span>
                <span className="vertical-tab-tag">{v.tagline}</span>
              </span>
            </button>
          ))}
        </div>
      </div>

      {!vertical && (
        <div className="vertical-gate">
          <div className="vertical-gate-inner">
            <div className="vertical-gate-icon">👋</div>
            <h2 className="vertical-gate-title">Pick your industry above to see your leads.</h2>
            <p className="vertical-gate-sub">
              The demo streams a realistic inbox of inbound leads for your vertical and runs each one through the 6-agent pipeline. Pricing, benchmarks, and sample data adjust to match.
            </p>
            <div className="vertical-gate-secondary">
              Want a preview first? <button className="vertical-gate-link" onClick={() => setShowCallSim(true)}>📞 Watch it answer a call</button>
            </div>
          </div>
        </div>
      )}

      {vertical && <Dashboard stats={stats} />}

      {vertical && showManual && (
        <div className="manual-form-wrapper">
          <LeadForm onRun={handleManualRun} loading={loading} />
        </div>
      )}

      {vertical && (
        <div className="call-cta-row">
          <button className="call-cta-btn" onClick={() => setShowCallSim(true)}>
            <span className="call-cta-icon">📞</span>
            <span className="call-cta-text">
              <span className="call-cta-title">Watch it answer a {VERTICALS[vertical].label} call</span>
              <span className="call-cta-sub">Staged voice demo with your industry's scenario</span>
            </span>
            <span className="call-cta-arrow">→</span>
          </button>
        </div>
      )}

      {showCallSim && (
        <CallSimulator vertical={vertical} onClose={() => setShowCallSim(false)} />
      )}

      {vertical && (
        <div className="main-grid">
          <Inbox
            inbox={inbox}
            activeLeadId={activeLead?.id}
            onSelect={(l) => !l.processing && runLead(l)}
            now={now}
          />
          <div className="pipeline-col">
            <Results
              result={result}
              loading={loading}
              error={error}
              revealedStage={revealedStage}
              activeLead={activeLead}
            />
          </div>
          <ActivityFeed events={activity} now={now} />
        </div>
      )}

      <RoiCalculator initialVertical={vertical || "septic"} key={vertical || "septic"} />

      <Integrations />

      <DemoVideos />

      <footer className="app-footer">
        <div className="footer-brand">
          <img src="/KeresLogo.png" alt="Keres" />
          <span>Keres · AI lead automation for septic, roofing & HVAC</span>
        </div>
        <div className="footer-meta">
          <a
            href="/portal-preview"
            onClick={(e) => { e.preventDefault(); navigate("/portal-preview"); }}
            className="footer-link"
          >See the customer portal →</a>
          <span>© {new Date().getFullYear()} Keres</span>
        </div>
      </footer>
    </div>
  );
}
