import React, { useEffect, useState } from "react";
import Upload from "./pages/Upload.jsx";

function useRoute() {
  const getPath = () => (typeof window !== "undefined" ? window.location.pathname : "/") || "/";
  const [path, setPath] = useState(getPath);
  useEffect(() => {
    const onPop = () => setPath(getPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const navigate = (to) => {
    window.history.pushState({}, "", to);
    setPath(to);
  };
  return [path, navigate];
}

export default function App() {
  const [path, navigate] = useRoute();
  const route = path.replace(/\/$/, "") || "/";

  return (
    <div className="lr-app">
      <header className="lr-header">
        <div className="lr-brand">
          <div className="lr-brand-mark">LR</div>
          <div>
            <div className="lr-brand-name">Lead Revival</div>
            <div className="lr-brand-sub">Wake up old leads · ship recovered revenue</div>
          </div>
        </div>
        <nav className="lr-nav">
          <a className={"lr-nav-link" + (route === "/" ? " active" : "")}
             href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }}>Upload</a>
          <a className={"lr-nav-link" + (route === "/campaigns" ? " active" : "")}
             href="/campaigns" onClick={(e) => { e.preventDefault(); navigate("/campaigns"); }}>Campaigns</a>
        </nav>
      </header>

      <main className="lr-main">
        {route === "/" && <Upload onCreated={(id) => navigate(`/campaigns/${id}`)} />}
        {route === "/campaigns" && <CampaignsPlaceholder />}
        {route.startsWith("/campaigns/") && <CampaignDetailPlaceholder id={route.split("/")[2]} />}
      </main>

      <footer className="lr-footer">
        Preview build · DEMO_MODE · no real SMS sent · no cards charged.
      </footer>
    </div>
  );
}

function CampaignsPlaceholder() {
  return (
    <div className="lr-card">
      <h2>Campaigns</h2>
      <p className="lr-muted">Campaign list + state counts land in M6.</p>
    </div>
  );
}

function CampaignDetailPlaceholder({ id }) {
  return (
    <div className="lr-card">
      <h2>Campaign #{id}</h2>
      <p className="lr-muted">Lead table, message threads, and ROI report land in M6.</p>
    </div>
  );
}
