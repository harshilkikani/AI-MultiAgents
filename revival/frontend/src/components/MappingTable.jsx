import React from "react";

const FIELD_LABEL = {
  name: "Name",
  phone: "Phone",
  email: "Email",
  source: "Lead source",
  last_contact: "Last contact",
  notes: "Notes",
};

const REQUIRED = new Set(["name"]);

export default function MappingTable({ preview, mapping, onChange }) {
  if (!preview) return null;
  const allHeaders = preview.all_headers || [];
  const fields = preview.canonical_fields || Object.keys(FIELD_LABEL);
  // Build effective view using the user's override on top of detected.
  const effective = { ...(preview.mapping || {}), ...(mapping || {}) };

  const setField = (canon, header) => {
    const next = { ...(mapping || {}) };
    if (!header) delete next[canon];
    else next[canon] = header;
    onChange?.(next);
  };

  return (
    <div className="lr-mapping">
      <div className="lr-mapping-head">
        <div>Canonical field</div>
        <div>CSV column</div>
      </div>
      {fields.map((canon) => {
        const selected = effective[canon] || "";
        return (
          <div key={canon} className={"lr-mapping-row" + (REQUIRED.has(canon) ? " required" : "")}>
            <label htmlFor={`map-${canon}`}>
              {FIELD_LABEL[canon] || canon}
              {REQUIRED.has(canon) && <span className="lr-req"> *</span>}
            </label>
            <select
              id={`map-${canon}`}
              value={selected}
              onChange={(e) => setField(canon, e.target.value)}
            >
              <option value="">— (unmapped)</option>
              {allHeaders.map((h) => (
                <option key={h} value={h}>{h}</option>
              ))}
            </select>
          </div>
        );
      })}
      {preview.unmapped_headers?.length > 0 && (
        <div className="lr-mapping-unused">
          <span>Unused CSV columns:</span>
          {preview.unmapped_headers.map((h) => (
            <span key={h} className="lr-chip">{h}</span>
          ))}
        </div>
      )}
    </div>
  );
}
