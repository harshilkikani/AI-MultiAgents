import React, { useEffect, useState } from "react";
import CampaignDetail from "./pages/CampaignDetail.jsx";
import CampaignList from "./pages/CampaignList.jsx";
import Demo from "./pages/Demo.jsx";
import Login from "./pages/Login.jsx";
import RoiReport from "./pages/RoiReport.jsx";
import Settings from "./pages/Settings.jsx";
import Upload from "./pages/Upload.jsx";
import HealthDot from "./components/HealthDot.jsx";
import { clearSession, getToken } from "./auth.js";
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

const PAGE_TITLES = {
  "/": "Upload · Lead Revival",
  "/campaigns": "Campaigns · Lead Revival",
  "/settings": "Settings · Lead Revival",
  "/demo": "Demo · Lead Revival",
  "/login": "Sign in · Lead Revival",
};

function titleForRoute(route) {
  if (PAGE_TITLES[route]) return PAGE_TITLES[route];
  if (route.endsWith("/report")) return "ROI report · Lead Revival";
  if (route.startsWith("/campaigns/")) return `Campaign #${route.split("/")[2]} · Lead Revival`;
  return "Lead Revival";
}

export default function App() {
  const [path, navigate] = useRoute();
  const route = path.replace(/\/$/, "") || "/";
  const isReport = route.startsWith("/campaigns/") && route.endsWith("/report");
  const isLogin = route === "/login";
  const ws = getWorkspace();
  const token = getToken();
  const inDemoWorkspace = ws === 2;

  // Sync the browser tab title with the route.
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.title = titleForRoute(route);
    }
  }, [route]);

  // Gate: if no session and we're not on a public route, redirect to login.
  useEffect(() => {
    const publicRoutes = ["/login", "/demo"];
    if (!token && !publicRoutes.includes(route)) {
      navigate("/login");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, route]);

  if (isLogin) return <Login navigate={navigate} />;

  // When user navigates away from /demo and /campaigns/*, drop back to
  // workspace 1 so "Upload" and "Campaigns" show their real workspace.
  const navigateAndScope = (to) => {
    if (to === "/" || to === "/campaigns") setWorkspace(1);
    navigate(to);
  };

  return (
    <div className="lr-app">
      {inDemoWorkspace && (
        <div className="lr-demo-banner no-print">
          <span className="lr-demo-badge">Preview</span>
          <span>
            Viewing the <strong>Hatcher Septic &amp; Drain</strong> demo workspace — read-only example.
          </span>
          <button className="lr-demo-exit" onClick={() => { setWorkspace(1); navigate("/"); }}>
            Exit demo →
          </button>
        </div>
      )}
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
          <a className={"lr-nav-link" + (route === "/settings" ? " active" : "")}
             href="/settings" onClick={(e) => { e.preventDefault(); navigateAndScope("/settings"); }}>Settings</a>
          <a className={"lr-nav-link" + (route === "/demo" ? " active" : "")}
             href="/demo" onClick={(e) => { e.preventDefault(); navigate("/demo"); }}>Demo</a>
          <button
            className="lr-nav-link lr-nav-logout"
            onClick={() => { clearSession(); setWorkspace(1); navigate("/login"); }}
          >Sign out</button>
          <HealthDot />
        </nav>
      </header>

      <main className="lr-main">
        {route === "/" && <Upload onCreated={(id) => navigate(`/campaigns/${id}`)} />}
        {route === "/demo" && <Demo navigate={navigate} />}
        {route === "/settings" && <Settings />}
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
