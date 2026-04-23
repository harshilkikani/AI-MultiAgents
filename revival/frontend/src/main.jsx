import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

// Tiny error boundary — without this, any render error = white screen with
// no feedback. This surfaces the error + stack in the DOM.
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Lead Revival crashed:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{
          padding: 32, background: "#15120d", color: "#f2ede2",
          fontFamily: "monospace", minHeight: "100vh",
        }}>
          <h1 style={{ color: "#ff6b6b", margin: 0 }}>Lead Revival — render error</h1>
          <p style={{ color: "#9c8f78" }}>
            Check the browser console for full stack. Backend is almost
            certainly fine; this is a frontend issue.
          </p>
          <pre style={{
            background: "#0b0a08", border: "1px solid #3a2e1e",
            padding: 16, borderRadius: 8, overflow: "auto", whiteSpace: "pre-wrap",
          }}>{String(this.state.error?.stack || this.state.error)}</pre>
          <button onClick={() => {
            try { window.localStorage.clear(); } catch {}
            window.location.href = "/login";
          }} style={{ marginTop: 16, padding: "10px 18px", background: "#e8793c",
                      color: "#0b0a08", border: 0, borderRadius: 8,
                      fontWeight: 700, cursor: "pointer" }}>
            Reset session + reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
