const API_BASE = import.meta.env.VITE_API_BASE || "";

function friendlyError(status, body) {
  try {
    const parsed = JSON.parse(body);
    if (Array.isArray(parsed?.detail)) {
      const msgs = parsed.detail.map(
        (d) => `${d.loc?.slice(1).join(".") || "field"}: ${d.msg}`
      );
      return msgs.join("; ");
    }
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch {}
  return `Server returned ${status}`;
}

export async function processLead(payload) {
  let res;
  try {
    res = await fetch(`${API_BASE}/api/process-lead`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    throw new Error(
      "Cannot reach the backend. Is it running on port 8000? " +
      "(Try: cd backend && uvicorn app.main:app --reload --port 8000)"
    );
  }
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(friendlyError(res.status, txt));
  }
  return res.json();
}

export async function fetchSampleLeads() {
  try {
    const res = await fetch(`${API_BASE}/api/sample-leads`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}
