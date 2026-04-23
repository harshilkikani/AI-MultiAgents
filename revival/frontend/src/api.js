import { getToken } from "./auth.js";
import { getWorkspace } from "./ws.js";

// Thin fetch wrapper. Throws on non-2xx so callers can .catch.
// Stamps the workspace and bearer token on every request.
async function http(path, opts = {}) {
  const headers = new Headers(opts.headers || {});
  const ws = getWorkspace();
  if (ws && ws !== 1) headers.set("X-Workspace-Id", String(ws));
  const token = getToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    // Session expired — clear token and let the app redirect to login.
    try { window.localStorage.removeItem("lr_session_token"); } catch {}
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.assign("/login");
    }
  }
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = await res.text(); }
    // Prefer the server's own detail message over the raw HTTP status line
    // — "Campaign not found" reads better than "404 Not Found — Campaign not
    // found". We keep the status code prefix for 5xx so ops can triage.
    const text = detail || res.statusText || "request failed";
    const prefix = res.status >= 500 ? `Server error (${res.status}): ` : "";
    const err = new Error(`${prefix}${text}`);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => http("/api/health"),

  createCampaign: (body) =>
    http("/api/campaigns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  listCampaigns: () => http("/api/campaigns"),
  getCampaign: (id) => http(`/api/campaigns/${id}`),

  previewLeads: (campaignId, file, mapping) => {
    const fd = new FormData();
    fd.append("file", file);
    if (mapping) fd.append("mapping", JSON.stringify(mapping));
    return http(`/api/campaigns/${campaignId}/leads/preview`, {
      method: "POST",
      body: fd,
    });
  },
  uploadLeads: (campaignId, file, mapping) => {
    const fd = new FormData();
    fd.append("file", file);
    if (mapping) fd.append("mapping", JSON.stringify(mapping));
    return http(`/api/campaigns/${campaignId}/leads/upload`, {
      method: "POST",
      body: fd,
    });
  },
  sampleGenerate: (campaignId, n = 3) =>
    http(`/api/campaigns/${campaignId}/sample-generate?n=${n}`, { method: "POST" }),
  listLeads: (campaignId, state) => {
    const q = state ? `?state=${encodeURIComponent(state)}` : "";
    return http(`/api/campaigns/${campaignId}/leads${q}`);
  },

  generate: (campaignId) =>
    http(`/api/campaigns/${campaignId}/generate`, { method: "POST" }),
  pauseCampaign: (campaignId) =>
    http(`/api/campaigns/${campaignId}/pause`, { method: "POST" }),
  resumeCampaign: (campaignId) =>
    http(`/api/campaigns/${campaignId}/resume`, { method: "POST" }),
  stats: (campaignId) => http(`/api/campaigns/${campaignId}/stats`),
  leadMessages: (campaignId, leadId) =>
    http(`/api/campaigns/${campaignId}/leads/${leadId}/messages`),
  campaignAudit: (campaignId, eventType) => {
    const q = eventType ? `?event_type=${encodeURIComponent(eventType)}` : "";
    return http(`/api/campaigns/${campaignId}/audit${q}`);
  },
  healthCheck: () => http("/api/health"),

  manualSend: (messageId) =>
    http(`/api/messages/${messageId}/send`, { method: "POST" }),

  checkout: (campaignId, plan = "one_shot") =>
    http(`/api/campaigns/${campaignId}/checkout?plan=${plan}`, { method: "POST" }),

  demoInfo: () => http("/api/demo/info"),
  demoReset: () => http("/api/demo/reset", { method: "POST" }),

  // Workspace settings
  getWorkspaceSettings: () => http("/api/workspace"),
  updateWorkspaceSettings: (body) =>
    http("/api/workspace", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // Integrations
  jobberStatus: () => http("/api/integrations/jobber"),
  jobberConnect: () => http("/api/integrations/jobber/connect", { method: "POST" }),
  jobberCallback: (url) => http(url),
  jobberDisconnect: () => http("/api/integrations/jobber/disconnect", { method: "POST" }),
  jobberSync: (campaignId, cutoff_days = 180) =>
    http(`/api/integrations/jobber/sync?campaign_id=${campaignId}&cutoff_days=${cutoff_days}`, { method: "POST" }),

  // Auth
  login: (email) => http("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  }),
  me: () => http("/api/auth/me"),
  logout: () => http("/api/auth/logout", { method: "POST" }),
};
