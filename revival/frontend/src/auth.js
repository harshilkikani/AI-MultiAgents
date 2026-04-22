// Session token storage. In DEMO_MODE the backend issues `demo-...` tokens
// synchronously; in prod it emails a magic link and the link's hash
// delivers a Supabase access token that we stash here.
const TOKEN_KEY = "lr_session_token";

export function getToken() {
  try {
    return typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;
  } catch {
    return null;
  }
}

export function setToken(t) {
  try {
    if (t) window.localStorage.setItem(TOKEN_KEY, t);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {}
}

export function isDemoToken(t) {
  return typeof t === "string" && t.startsWith("demo-");
}

export function clearSession() {
  setToken(null);
}
