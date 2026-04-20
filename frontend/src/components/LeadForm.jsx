import React, { useState } from "react";

export default function LeadForm({ onRun, loading }) {
  const [message, setMessage] = useState("");
  const [source, setSource] = useState("");
  const [budget, setBudget] = useState("");
  const [service, setService] = useState("");
  const [urgency, setUrgency] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");

  const submit = (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    onRun({
      message: message.trim(),
      source: source || null,
      budget: budget || null,
      service_requested: service || null,
      urgency: urgency || null,
      contact_name: contactName || null,
      contact_email: contactEmail || null,
    });
    setMessage("");
  };

  return (
    <form className="card" onSubmit={submit}>
      <div className="card-head">
        <h2>Add a manual lead</h2>
      </div>

      <label>Message</label>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Paste the lead's inquiry..."
        required
      />

      <div className="row">
        <div>
          <label>Contact name</label>
          <input value={contactName} onChange={(e) => setContactName(e.target.value)} placeholder="Jane Doe" />
        </div>
        <div>
          <label>Contact email</label>
          <input value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} placeholder="jane@example.com" />
        </div>
      </div>

      <div className="row">
        <div>
          <label>Source</label>
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="website form" />
        </div>
        <div>
          <label>Urgency</label>
          <select value={urgency} onChange={(e) => setUrgency(e.target.value)}>
            <option value="">—</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>

      <div className="row">
        <div>
          <label>Service requested</label>
          <input value={service} onChange={(e) => setService(e.target.value)} placeholder="e.g. AI assistant" />
        </div>
        <div>
          <label>Budget</label>
          <input value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="e.g. $500/mo" />
        </div>
      </div>

      <button className="btn" type="submit" disabled={loading} style={{ marginTop: 14, width: "100%" }}>
        {loading ? "Processing..." : "Inject lead into inbox"}
      </button>
    </form>
  );
}
