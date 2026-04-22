// Workspace selector — stored in localStorage so refresh/nav keeps the
// user in the demo workspace once they land on /demo. api.js reads from
// this on every request.
const KEY = "lr_workspace_id";

export function getWorkspace() {
  try {
    const v = typeof window !== "undefined" ? window.localStorage.getItem(KEY) : null;
    const n = Number(v);
    return Number.isFinite(n) && n > 0 ? n : 1;
  } catch {
    return 1;
  }
}

export function setWorkspace(id) {
  try {
    if (!id || id === 1) window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, String(id));
  } catch {}
}
