import React from "react";

export default function LeadTable({ leads, onPick }) {
  if (!leads?.length) {
    return <div className="lr-empty">No leads in this bucket.</div>;
  }
  return (
    <table className="lr-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Phone</th>
          <th>Email</th>
          <th>Source</th>
          <th>Last contact</th>
          <th>State</th>
        </tr>
      </thead>
      <tbody>
        {leads.map((l) => (
          <tr key={l.id} className="lr-row-clickable" onClick={() => onPick?.(l)}>
            <td>{l.name}</td>
            <td className="lr-mono">{l.phone || <span className="lr-muted">—</span>}</td>
            <td>{l.email || <span className="lr-muted">—</span>}</td>
            <td>{l.source || <span className="lr-muted">—</span>}</td>
            <td className="lr-mono">{l.last_contact || <span className="lr-muted">—</span>}</td>
            <td><span className="lr-tag">{l.state}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
