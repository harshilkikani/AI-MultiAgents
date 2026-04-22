import React, { useEffect, useState } from "react";
import CampaignDetail from "./pages/CampaignDetail.jsx";
import CampaignList from "./pages/CampaignList.jsx";
import Demo from "./pages/Demo.jsx";
import RoiReport from "./pages/RoiReport.jsx";
import Upload from "./pages/Upload.jsx";
import { getWorkspace, setWorkspace } from "./ws.js";

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
  const isReport = route.startsWith("/campaigns/") && route.endsWith("/report");
  const isDemo = route === "/demo";
  const ws = getWorkspace();

  // When user navigates away from /demo and /campaigns/*, drop back to
  // workspace 1 so "Upload" and "Campaigns" show their real workspace.
  const navigateAndScope = (to) => {
    if (to === "/" || to === "/campaigns") setWorkspace(1);
    navigate(to);
  };

  return (
    <div className="lr-app">
      {isDemo || ws !== 1 ? (
        <div className="lr-demo-banner no-print">
          <span className="lr-demo-badge">Preview</span>
          <span>
            Viewing the <strong>Hatcher Septic &amp; Drain</strong> demo workspace — read-only example.
          </span>
          <button className="lr-demo-exit" onClick={() => { setWorkspace(1); navigate("/"); }}>
            Exit demo →
          </button>
        </div>
      ) : null}
      <header className="lr-header no-print">
        <div className="lr-brand">
          <div className="lr-brand-mark">LR</div>
          <div>
            <div className="lr-brand-name">Lead Revival</div>
            <div className="lr-brand-sub">Wake up old leads · ship recovered revenue</div>
          </div>
        </div>
        <nav className="lr-nav">
          <a className={"lr-nav-link" + (route === "/" ? " active" : "")}
             href="/" onClick={(e) => { e.preventDefault(); navigateAndScope("/"); }}>Upload</a>
          <a className={"lr-nav-link" + (route === "/campaigns" ? " active" : "")}
             href="/campaigns" onClick={(e) => { e.preventDefault(); navigateAndScope("/campaigns"); }}>Campaigns</a>
          <a className={"lr-nav-link" + (route === "/demo" ? " active" : "")}
             href="/demo" onClick={(e) => { e.preventDefault(); navigate("/demo"); }}>Demo</a>
        </nav>
      </header>

      <main className="lr-main">
        {route === "/" && <Upload onCreated={(id) => navigate(`/campaigns/${id}`)} />}
        {route === "/demo" && <Demo navigate={navigate} />}
        {route === "/campaigns" && <CampaignList onPick={(id) => navigate(`/campaigns/${id}`)} />}
        {route.startsWith("/campaigns/") && !isReport && (
          <CampaignDetail
            id={Number(route.split("/")[2])}
            onOpenReport={(id) => navigate(`/campaigns/${id}/report`)}
          />
        )}
        {isReport && (
          <RoiReport
            id={Number(route.split("/")[2])}
            onBack={() => navigate(`/campaigns/${route.split("/")[2]}`)}
          />
        )}
      </main>

      <footer className="lr-footer no-print">
        Preview build · DEMO_MODE · no real SMS sent · no cards charged.
      </footer>
    </div>
  );
}
