import React, { useEffect, useState } from "react";
import CampaignDetail from "./pages/CampaignDetail.jsx";
import CampaignList from "./pages/CampaignList.jsx";
import RoiReport from "./pages/RoiReport.jsx";
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
  const isReport = route.startsWith("/campaigns/") && route.endsWith("/report");

  return (
    <div className="lr-app">
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
             href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }}>Upload</a>
          <a className={"lr-nav-link" + (route === "/campaigns" ? " active" : "")}
             href="/campaigns" onClick={(e) => { e.preventDefault(); navigate("/campaigns"); }}>Campaigns</a>
        </nav>
      </header>

      <main className="lr-main">
        {route === "/" && <Upload onCreated={(id) => navigate(`/campaigns/${id}`)} />}
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
