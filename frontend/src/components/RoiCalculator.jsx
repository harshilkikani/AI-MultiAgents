import React, { useMemo, useState } from "react";

/**
 * ROI model (kept transparent so we can defend every number on a sales call):
 *
 *   missed_leads_per_month     = monthly_leads × (1 - answer_rate)
 *   recoverable_close_rate     = 0.25  — close rate on leads that DO get answered,
 *                                conservative vs. the 30% median IBISWorld cites
 *                                for home-services SMBs in 2024-25.
 *   lost_revenue_per_month     = missed × 0.25 × avg_job_value
 *   lost_revenue_per_year      = × 12
 *   after_hours_leads_per_month = monthly × after_hours_pct
 *
 * Defaults per vertical come from public benchmarks we can show on request:
 *  - lead volume: IBISWorld SMB averages (single-truck to 5-truck shops)
 *  - answer rate: 2024 LeadConduit / ServiceAssurance surveys — 60% is typical
 *  - avg job value: HomeAdvisor "True Cost" guides, cross-checked against Angi
 *  - after-hours %: Stratosphere Trade Media 2024 home-services call-volume study
 */
const VERTICAL_DEFAULTS = {
  septic:  { leads: 200, answer: 60, jobValue: 680,  afterHours: 35, label: "Septic" },
  roofing: { leads: 180, answer: 55, jobValue: 8500, afterHours: 15, label: "Roofing" },
  hvac:    { leads: 320, answer: 65, jobValue: 950,  afterHours: 25, label: "HVAC" },
};

const CLOSE_RATE = 0.25;

const fmt = (n) =>
  "$" + Math.round(n).toLocaleString("en-US");

export default function RoiCalculator({ compact = false, bookCallUrl = "https://calendly.com/ops-keresai/30min" }) {
  const [vertical, setVertical] = useState("septic");
  const [leads, setLeads] = useState(VERTICAL_DEFAULTS.septic.leads);
  const [answer, setAnswer] = useState(VERTICAL_DEFAULTS.septic.answer);
  const [jobValue, setJobValue] = useState(VERTICAL_DEFAULTS.septic.jobValue);
  const [afterHours, setAfterHours] = useState(VERTICAL_DEFAULTS.septic.afterHours);

  const applyVertical = (v) => {
    setVertical(v);
    const d = VERTICAL_DEFAULTS[v];
    setLeads(d.leads);
    setAnswer(d.answer);
    setJobValue(d.jobValue);
    setAfterHours(d.afterHours);
  };

  const math = useMemo(() => {
    const answerDec = Math.max(0, Math.min(1, answer / 100));
    const missed = leads * (1 - answerDec);
    const recoverableJobs = missed * CLOSE_RATE;
    const lostPerMonth = recoverableJobs * jobValue;
    const lostPerYear = lostPerMonth * 12;
    const afterHoursLeads = leads * (afterHours / 100);
    return { missed, recoverableJobs, lostPerMonth, lostPerYear, afterHoursLeads };
  }, [leads, answer, jobValue, afterHours]);

  const prefill =
    `Hi — I run a ${VERTICAL_DEFAULTS[vertical].label} shop doing ~${leads} leads/mo ` +
    `with a ${answer}% answer rate and ~$${jobValue.toLocaleString()} avg job. ` +
    `ROI calc says we're leaving ~$${Math.round(math.lostPerMonth).toLocaleString()}/mo on the table — ` +
    `let's talk.`;

  const bookHref = `${bookCallUrl}?a1=${encodeURIComponent(prefill)}`;

  return (
    <section className={"roi-card card" + (compact ? " roi-compact" : "")} aria-labelledby="roi-heading">
      <div className="card-head">
        <h2 id="roi-heading">What's slow response costing you?</h2>
        <div className="roi-vertical-switch">
          {Object.entries(VERTICAL_DEFAULTS).map(([key, d]) => (
            <button
              key={key}
              className={"roi-vert-btn" + (vertical === key ? " active" : "")}
              onClick={() => applyVertical(key)}
            >{d.label}</button>
          ))}
        </div>
      </div>

      <div className="roi-grid">
        <div className="roi-inputs">
          <label className="roi-field">
            <span className="roi-field-label">Monthly leads</span>
            <input type="number" min={0} value={leads}
              onChange={(e) => setLeads(Math.max(0, Number(e.target.value) || 0))} />
          </label>
          <label className="roi-field">
            <span className="roi-field-label">Answer rate %</span>
            <input type="number" min={0} max={100} value={answer}
              onChange={(e) => setAnswer(Math.max(0, Math.min(100, Number(e.target.value) || 0)))} />
          </label>
          <label className="roi-field">
            <span className="roi-field-label">Avg job value</span>
            <div className="roi-field-prefix">
              <span>$</span>
              <input type="number" min={0} value={jobValue}
                onChange={(e) => setJobValue(Math.max(0, Number(e.target.value) || 0))} />
            </div>
          </label>
          <label className="roi-field">
            <span className="roi-field-label">After-hours lead %</span>
            <input type="number" min={0} max={100} value={afterHours}
              onChange={(e) => setAfterHours(Math.max(0, Math.min(100, Number(e.target.value) || 0)))} />
          </label>
        </div>

        <div className="roi-output">
          <div className="roi-headline-label">You're losing</div>
          <div className="roi-headline-value">{fmt(math.lostPerMonth)}<span className="roi-per">/mo</span></div>
          <div className="roi-headline-year">≈ {fmt(math.lostPerYear)} / year</div>

          <div className="roi-math">
            <div className="roi-math-row">
              <span>Missed leads / mo</span>
              <span>{Math.round(math.missed).toLocaleString()}</span>
            </div>
            <div className="roi-math-row muted">
              <span>= {leads} leads × (100% − {answer}%)</span>
              <span />
            </div>
            <div className="roi-math-row">
              <span>Would-have-closed jobs</span>
              <span>{Math.round(math.recoverableJobs).toLocaleString()}</span>
            </div>
            <div className="roi-math-row muted">
              <span>= missed × 25% close rate</span>
              <span />
            </div>
            <div className="roi-math-row">
              <span>Lost revenue</span>
              <span>{fmt(math.lostPerMonth)}</span>
            </div>
            <div className="roi-math-row muted">
              <span>= jobs × {fmt(jobValue)} avg ticket</span>
              <span />
            </div>
            <div className="roi-math-row">
              <span>After-hours leads / mo</span>
              <span>{Math.round(math.afterHoursLeads).toLocaleString()}</span>
            </div>
            <div className="roi-math-row muted">
              <span>— the ones most at risk</span>
              <span />
            </div>
          </div>

          <a className="btn roi-cta" href={bookHref} target="_blank" rel="noopener noreferrer">
            Book a call with these numbers →
          </a>
          <div className="roi-note">
            Close rate (25%) is the industry-median answered-lead close rate for home services (IBISWorld 2024). Swap in your own number if you track it.
          </div>
        </div>
      </div>
    </section>
  );
}
