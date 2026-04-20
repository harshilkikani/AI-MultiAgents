import React from "react";

// Replace the `videoUrl` fields below with your actual YouTube/Vimeo/Loom embed URLs
// once the demo videos are posted. Until then, each card shows a themed placeholder.
const DEMOS = [
  {
    id: "septic",
    industry: "Septic",
    title: "How Keres handles septic emergency calls at 2am",
    blurb:
      "Watch a live septic pumping request route from Facebook Lead Ad to booked job in under 45 seconds — even after hours.",
    stat: "+38% jobs captured after 6pm",
    videoUrl: null, // e.g. "https://www.youtube.com/embed/XXXXXX"
    tint: "#e8793c",
  },
  {
    id: "roofing",
    industry: "Roofing",
    title: "Storm surge: 60 roofing leads in one day, zero missed",
    blurb:
      "See Keres triage a full day of storm-damage inspection requests, escalate the hot ones to sales, and nurture the rest — all without a human touching the inbox.",
    stat: "0 missed inspections during hailstorm surge",
    videoUrl: null,
    tint: "#5eead4",
  },
  {
    id: "hvac",
    industry: "HVAC",
    title: "HVAC peak season: auto-book service calls 24/7",
    blurb:
      "Watch Keres qualify an emergency AC repair lead, send a personalized quote range, and drop the booking straight into the techs' schedule.",
    stat: "Avg response time: 34s (vs. 4h 12m industry)",
    videoUrl: null,
    tint: "#7c9cff",
  },
];

function VideoFrame({ demo }) {
  if (demo.videoUrl) {
    return (
      <div className="video-wrap">
        <iframe
          src={demo.videoUrl}
          title={`${demo.industry} demo — ${demo.title}`}
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
        />
      </div>
    );
  }
  return (
    <div className="video-placeholder" style={{ borderColor: demo.tint + "55" }}>
      <div className="video-placeholder-play" style={{ background: demo.tint }}>▶</div>
      <div className="video-placeholder-label">{demo.industry} demo · coming soon</div>
    </div>
  );
}

export default function DemoVideos() {
  return (
    <section className="demo-videos" aria-labelledby="demos-heading">
      <div className="demo-videos-head">
        <h2 id="demos-heading">Watch Keres in action</h2>
        <p>
          Three real demos, one per industry we serve today. Each one shows a real lead coming in and being
          handled end-to-end — qualified, replied to, and routed — in under a minute.
        </p>
      </div>

      <div className="demo-videos-grid">
        {DEMOS.map((d) => (
          <article key={d.id} className="demo-video-card">
            <VideoFrame demo={d} />
            <div className="demo-video-body">
              <div className="demo-video-industry" style={{ color: d.tint }}>{d.industry}</div>
              <h3>{d.title}</h3>
              <p>{d.blurb}</p>
              <div className="demo-video-stat">{d.stat}</div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
