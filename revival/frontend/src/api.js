// Thin fetch wrapper. Throws on non-2xx so callers can .catch.
async function http(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = await res.text(); }
    throw new Error(`${res.status} ${res.statusText} — ${detail || "request failed"}`);
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

  uploadLeads: (campaignId, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return http(`/api/campaigns/${campaignId}/leads/upload`, {
      method: "POST",
      body: fd,
    });
  },
  listLeads: (campaignId, state) => {
    const q = state ? `?state=${encodeURIComponent(state)}` : "";
    return http(`/api/campaigns/${campaignId}/leads${q}`);
  },
};
