import React, { useEffect, useRef, useState } from "react";

/**
 * Call scripts are hand-authored, vertical-specific staged conversations.
 * Timings are in ms. Panel events fire at specific cursor positions in the
 * transcript so the side panel feels reactive to what the agent "heard".
 *
 * Revenue estimates are defensible ranges sourced from public home-services
 * benchmarks (HomeAdvisor, Angi, industry trade pubs) — methodology notes inline.
 */
const SCRIPTS = {
  septic: {
    vertical: "Septic",
    caller: "Darlene Hatcher",
    callerCity: "Moultrie, GA",
    phone: "(229) 555-0142",
    scenario: "Emergency backup · after-hours",
    // Septic emergency pump average $450–$900 (HomeAdvisor national 2025);
    // we pick $680 as a mid-market round number for a 1,000-gal tank.
    estRevenue: 680,
    durationSec: 47,
    lines: [
      { who: "keres", text: "Hatcher Septic & Drain, this is Aria — how can I help?", delay: 350 },
      { who: "caller", text: "Hi, uh, I think my septic is backing up into my basement. It smells terrible. Please tell me you're open.", delay: 220 },
      { who: "keres", text: "I'm so sorry — that is an emergency and yes, we have a truck that can run tonight. Can I grab your address and a number to text?", delay: 260 },
      { who: "caller", text: "Yeah it's 412 Willow Bend Drive, Moultrie. Phone's 2295550142.", delay: 220 },
      { who: "keres", text: "Got it. Tank size on file looks like 1,000 gallons, last pump was 2022 — does that sound right?", delay: 240 },
      { who: "caller", text: "Yeah, I think that's right. Can you come now?", delay: 180 },
      { who: "keres", text: "Truck 3 with Marcus can be there by 6:45 AM — first slot of the day. Emergency pump runs $680 all-in. Should I book it?", delay: 260 },
      { who: "caller", text: "Yes, please, anything. Book it.", delay: 160 },
      { who: "keres", text: "Booked. You'll get a text in 30 seconds with Marcus's ETA and the invoice link. Try not to run any water tonight. You're good.", delay: 260 },
    ],
    panelEvents: [
      { afterLine: 1, kind: "detect",  label: "Caller ID match",        detail: "Existing customer · Darlene Hatcher" },
      { afterLine: 2, kind: "detect",  label: "Intent detected",        detail: "Emergency septic backup" },
      { afterLine: 2, kind: "qualify", label: "Qualifying urgency…",    detail: "P0 — active overflow, health risk" },
      { afterLine: 4, kind: "lookup",  label: "CRM pulled",             detail: "Tank: 1,000 gal · last pump 2022-08" },
      { afterLine: 6, kind: "schedule",label: "Checking calendar",      detail: "Nearest slot: Truck 3 · 6:45 AM" },
      { afterLine: 7, kind: "quote",   label: "Quote generated",        detail: "$680 emergency pump (standard pricing)" },
      { afterLine: 8, kind: "book",    label: "Booking confirmed",      detail: "Job #4421 → ServiceTitan" },
      { afterLine: 8, kind: "message", label: "SMS sent to caller",     detail: "ETA + invoice link · Twilio" },
    ],
  },

  roofing: {
    vertical: "Roofing",
    caller: "Mike Calloway",
    callerCity: "Denver, CO",
    phone: "(303) 555-0199",
    scenario: "Storm-damage inspection request",
    // Avg residential roof replacement estimate ticket $9k–$18k (IBISWorld
    // 2025); inspection-to-close rate ~30% post-hail. We log lead value,
    // not close value, at $4,200 (expected value @ 30% close of $14k job).
    estRevenue: 4200,
    durationSec: 52,
    lines: [
      { who: "keres", text: "Ironridge Roofing, this is Aria. Are you calling about last Tuesday's hail?", delay: 320 },
      { who: "caller", text: "Yeah, actually. My neighbor said you guys inspected their roof — mine's got dents all over the gutters.", delay: 220 },
      { who: "keres", text: "You're in good hands. Free inspection, no obligation. What's the address?", delay: 240 },
      { who: "caller", text: "2847 Kipling Street, Denver. Single story, asphalt shingle.", delay: 200 },
      { who: "keres", text: "Great — and is this covered under a homeowner's policy you'd want us to help document?", delay: 240 },
      { who: "caller", text: "Yeah, State Farm. Claim's already filed but I haven't picked a contractor.", delay: 220 },
      { who: "keres", text: "Perfect. I can get Tom out Thursday at 10 AM for a full inspection — drone photos, insurance-ready report, about 45 minutes. Sound good?", delay: 280 },
      { who: "caller", text: "Thursday 10 works. Do I need to be home?", delay: 180 },
      { who: "keres", text: "Exterior only, so no — but Tom will text you 20 minutes before arrival. You'll get the full photo report by 5 PM Thursday.", delay: 260 },
    ],
    panelEvents: [
      { afterLine: 0, kind: "detect",  label: "Storm campaign active",   detail: "Denver hail · Apr 16, 2026" },
      { afterLine: 2, kind: "detect",  label: "Intent detected",         detail: "Hail inspection · referral" },
      { afterLine: 3, kind: "qualify", label: "Qualifying property",     detail: "Single story asphalt · standard scope" },
      { afterLine: 5, kind: "qualify", label: "Insurance confirmed",     detail: "State Farm · claim open · high intent" },
      { afterLine: 6, kind: "schedule",label: "Inspection slot held",    detail: "Tom · Thursday 10:00 AM" },
      { afterLine: 8, kind: "book",    label: "Job created",             detail: "Inspection #8801 → JobNimbus" },
      { afterLine: 8, kind: "message", label: "Confirmation sent",       detail: "Email + SMS · Twilio + SendGrid" },
      { afterLine: 8, kind: "quote",   label: "Est. job value logged",   detail: "~$14k replacement · $4.2k EV" },
    ],
  },

  hvac: {
    vertical: "HVAC",
    caller: "Priya Shah",
    callerCity: "Phoenix, AZ",
    phone: "(602) 555-0177",
    scenario: "AC out · 108° forecast",
    // HVAC emergency service call $300-$600, with parts avg $1,200 total
    // (ACCA 2024 benchmarks). Pick $950 — diagnostic + condenser fan cap.
    estRevenue: 950,
    durationSec: 44,
    lines: [
      { who: "keres", text: "Shah Heating & Air, this is Aria — are you out of cool?", delay: 320 },
      { who: "caller", text: "Yeah, AC died around midnight. It's already 88 inside and it's supposed to hit 108 today. Two kids in the house.", delay: 240 },
      { who: "keres", text: "That's a P0 for us. What's the address and is the outdoor unit running at all?", delay: 260 },
      { who: "caller", text: "1844 East Bell Road. Outdoor unit's humming but not spinning. Fan looks stuck.", delay: 220 },
      { who: "keres", text: "Sounds like a capacitor or fan motor — 80% of the time it's a same-day fix. I can route a tech to you in the next 90 minutes for a $950 diagnostic-plus-parts cap. OK to dispatch?", delay: 300 },
      { who: "caller", text: "Yes, absolutely, do it.", delay: 160 },
      { who: "keres", text: "Dispatched. Diego is finishing up on Camelback, then he's rolling to you — ETA 9:40 AM. You'll get live tracking by text.", delay: 260 },
      { who: "caller", text: "Thank you so much. Seriously.", delay: 180 },
      { who: "keres", text: "Stay hydrated, close south-facing blinds, run ceiling fans counter-clockwise. We're on it.", delay: 240 },
    ],
    panelEvents: [
      { afterLine: 1, kind: "detect",  label: "Intent detected",         detail: "AC failure · household with minors" },
      { afterLine: 1, kind: "qualify", label: "Priority bumped",         detail: "P0 · heat advisory in effect" },
      { afterLine: 3, kind: "lookup",  label: "Symptom matched",         detail: "Outdoor fan stalled → likely capacitor" },
      { afterLine: 4, kind: "schedule",label: "Technician routed",       detail: "Diego · ETA 9:40 AM (90 min)" },
      { afterLine: 4, kind: "quote",   label: "Service quote locked",    detail: "$950 diagnostic + parts cap" },
      { afterLine: 6, kind: "book",    label: "Dispatch created",        detail: "Job #2205 → Housecall Pro" },
      { afterLine: 6, kind: "message", label: "Live tracking SMS sent",  detail: "Twilio · ETA updates every 10 min" },
    ],
  },
};

const PANEL_ICONS = {
  detect: "🎯",
  qualify: "⚖️",
  lookup: "📇",
  schedule: "📆",
  quote: "💲",
  book: "✅",
  message: "✉️",
};

function useIsMounted() {
  const ref = useRef(true);
  useEffect(() => () => { ref.current = false; }, []);
  return ref;
}

export default function CallSimulator({ vertical, onClose }) {
  // Vertical prop can be "septic" / "roofing" / "hvac" — or null to let user pick.
  const initial = vertical && SCRIPTS[vertical] ? vertical : null;
  const [chosen, setChosen] = useState(initial);
  const [stage, setStage] = useState("idle"); // idle → ringing → live → ended
  const [transcript, setTranscript] = useState([]); // [{ who, text, partial? }]
  const [panel, setPanel] = useState([]);
  const [elapsed, setElapsed] = useState(0);
  const mountedRef = useIsMounted();
  const timersRef = useRef([]);
  const transcriptBottomRef = useRef(null);

  const script = chosen ? SCRIPTS[chosen] : null;

  const clearTimers = () => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
  };

  useEffect(() => () => clearTimers(), []);

  // Esc to close
  useEffect(() => {
    const h = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  // Elapsed clock while live
  useEffect(() => {
    if (stage !== "live") return;
    const start = Date.now();
    const iv = setInterval(() => {
      if (!mountedRef.current) return;
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(iv);
  }, [stage]);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptBottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript]);

  const pushTimer = (fn, ms) => {
    const t = setTimeout(() => {
      if (mountedRef.current) fn();
    }, ms);
    timersRef.current.push(t);
    return t;
  };

  const startCall = () => {
    if (!script) return;
    setTranscript([]);
    setPanel([]);
    setElapsed(0);
    setStage("ringing");

    // Ringing tone — 2 rings then pickup
    playRingtone(2);

    pushTimer(() => {
      setStage("live");
      playPickupBeep();
      runLines();
    }, 2400);
  };

  const runLines = () => {
    let cursor = 0;
    const lines = script.lines;
    const panelByLine = {};
    script.panelEvents.forEach((ev) => {
      panelByLine[ev.afterLine] = panelByLine[ev.afterLine] || [];
      panelByLine[ev.afterLine].push(ev);
    });

    const streamLine = (lineIdx) => {
      if (lineIdx >= lines.length) {
        pushTimer(() => setStage("ended"), 800);
        return;
      }
      const line = lines[lineIdx];
      const words = line.text.split(" ");
      setTranscript((prev) => [...prev, { who: line.who, text: "", partial: true }]);

      // Word-by-word reveal — caller voice 58ms/word, Keres 72ms/word
      const perWord = line.who === "keres" ? 72 : 58;
      let w = 0;
      const tick = () => {
        w += 1;
        setTranscript((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1];
          last.text = words.slice(0, w).join(" ");
          if (w >= words.length) last.partial = false;
          return next;
        });
        if (w < words.length) {
          pushTimer(tick, perWord + Math.random() * 30);
        } else {
          // Fire panel events attached to this line
          (panelByLine[lineIdx] || []).forEach((ev, i) => {
            pushTimer(() => {
              setPanel((prev) => [...prev, { ...ev, id: `p-${lineIdx}-${i}-${Date.now()}` }]);
            }, 120 + i * 180);
          });
          pushTimer(() => streamLine(lineIdx + 1), line.delay || 250);
        }
      };
      // Voice optional — nothing speaks by default to keep demos quiet.
      tick();
    };

    streamLine(0);
  };

  const reset = () => {
    clearTimers();
    setTranscript([]);
    setPanel([]);
    setElapsed(0);
    setStage("idle");
  };

  const formatTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="call-sim-backdrop" role="dialog" aria-modal="true" aria-label="Live call simulator">
      <div className="call-sim-modal">
        <div className="call-sim-head">
          <div className="call-sim-title">
            <span className="call-sim-pulse" />
            {stage === "idle" && "Demo call — pick a scenario"}
            {stage === "ringing" && "Incoming call…"}
            {stage === "live" && `Live · ${script.vertical} · ${formatTime(elapsed)}`}
            {stage === "ended" && `Call ended · ${formatTime(script.durationSec)}`}
          </div>
          <button className="call-sim-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {stage === "idle" && (
          <div className="call-sim-picker">
            <div className="call-sim-picker-hint">
              Staged demo — scripted calls, real pipeline behavior. Pick a scenario.
            </div>
            <div className="call-sim-picker-grid">
              {Object.entries(SCRIPTS).map(([key, s]) => (
                <button
                  key={key}
                  className="call-sim-picker-card"
                  onClick={() => { setChosen(key); }}
                >
                  <div className="call-sim-picker-industry">{s.vertical}</div>
                  <div className="call-sim-picker-scenario">{s.scenario}</div>
                  <div className="call-sim-picker-meta">
                    {s.caller} · {s.callerCity}
                  </div>
                </button>
              ))}
            </div>
            {chosen && (
              <button className="btn" onClick={startCall} style={{ marginTop: 14 }}>
                ▶ Answer call — {SCRIPTS[chosen].vertical}
              </button>
            )}
          </div>
        )}

        {stage !== "idle" && (
          <div className="call-sim-body">
            <div className="call-sim-transcript-col">
              <div className="call-sim-caller-strip">
                <div className="call-sim-caller-avatar">
                  {script.caller.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                </div>
                <div>
                  <div className="call-sim-caller-name">{script.caller}</div>
                  <div className="call-sim-caller-meta">{script.phone} · {script.callerCity}</div>
                </div>
                <div className="call-sim-caller-scenario">{script.scenario}</div>
              </div>

              <div className="call-sim-transcript">
                {stage === "ringing" && (
                  <div className="call-sim-ringing">
                    <div className="ringing-dots"><span /><span /><span /></div>
                    Ringing…
                  </div>
                )}
                {transcript.map((ln, i) => (
                  <div key={i} className={`call-line call-line-${ln.who}`}>
                    <span className="call-line-who">
                      {ln.who === "keres" ? "Aria (Keres)" : script.caller.split(" ")[0]}
                    </span>
                    <span className="call-line-text">
                      {ln.text}
                      {ln.partial && <span className="call-cursor">▋</span>}
                    </span>
                  </div>
                ))}
                <div ref={transcriptBottomRef} />
              </div>

              {stage === "ended" && (
                <div className="call-sim-endcard">
                  <div className="endcard-left">
                    <div className="endcard-label">Call ended</div>
                    <div className="endcard-duration">{formatTime(script.durationSec)}</div>
                  </div>
                  <div className="endcard-divider" />
                  <div className="endcard-middle">
                    <div className="endcard-label">Outcome</div>
                    <div className="endcard-outcome">Job booked</div>
                  </div>
                  <div className="endcard-divider" />
                  <div className="endcard-right">
                    <div className="endcard-label">Est. revenue</div>
                    <div className="endcard-revenue">${script.estRevenue.toLocaleString()}</div>
                  </div>
                  <button className="btn" onClick={reset} style={{ marginLeft: "auto" }}>
                    Run another
                  </button>
                </div>
              )}
            </div>

            <div className="call-sim-panel">
              <div className="call-sim-panel-head">Agent activity</div>
              {panel.length === 0 && (
                <div className="call-sim-panel-empty">Listening…</div>
              )}
              {panel.map((ev) => (
                <div key={ev.id} className={`call-sim-panel-row panel-${ev.kind}`}>
                  <div className="panel-icon">{PANEL_ICONS[ev.kind] || "•"}</div>
                  <div className="panel-body">
                    <div className="panel-label">{ev.label}</div>
                    <div className="panel-detail">{ev.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="call-sim-foot">
          Scripted demo — no real phone line. Underlying pipeline (intent, routing, booking, SMS) is the same one the product runs.
        </div>
      </div>
    </div>
  );
}

/* ───────────── Audio helpers — WebAudio; no assets required ───────────── */

let _audioCtx = null;
function audioCtx() {
  if (typeof window === "undefined") return null;
  if (_audioCtx) return _audioCtx;
  try {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    _audioCtx = new Ctor();
    return _audioCtx;
  } catch {
    return null;
  }
}

function playRingtone(rings = 2) {
  const ctx = audioCtx();
  if (!ctx) return;
  // US ringback: 440 + 480 Hz, 2s on / 4s off — we compress to ~1s on / 0.2s off.
  for (let r = 0; r < rings; r++) {
    const start = ctx.currentTime + r * 1.15;
    [440, 480].forEach((freq) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.08, start + 0.04);
      gain.gain.linearRampToValueAtTime(0.08, start + 0.95);
      gain.gain.linearRampToValueAtTime(0, start + 1.0);
      osc.connect(gain).connect(ctx.destination);
      osc.start(start);
      osc.stop(start + 1.05);
    });
  }
}

function playPickupBeep() {
  const ctx = audioCtx();
  if (!ctx) return;
  const start = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = 880;
  gain.gain.setValueAtTime(0, start);
  gain.gain.linearRampToValueAtTime(0.1, start + 0.02);
  gain.gain.linearRampToValueAtTime(0, start + 0.18);
  osc.connect(gain).connect(ctx.destination);
  osc.start(start);
  osc.stop(start + 0.2);
}
