import type { TendencyData, TendencyType } from "../../types";

const TENDENCY_TYPES: TendencyType[] = [
  "constant", "linear", "smooth",
  "sine-wave", "square-wave", "sawtooth-wave", "triangle-wave",
  "piecewise",
];

const TENDENCY_FIELDS: Record<TendencyType, string[]> = {
  constant:       ["duration", "value"],
  linear:         ["duration", "from", "to"],
  smooth:         ["duration", "from", "to"],
  "sine-wave":    ["duration", "base", "amplitude", "frequency", "phase"],
  "square-wave":  ["duration", "base", "amplitude", "frequency"],
  "sawtooth-wave":["duration", "base", "amplitude", "frequency"],
  "triangle-wave":["duration", "base", "amplitude", "frequency"],
  piecewise:      ["duration"],
};

interface Props {
  tendencies: TendencyData[];
  onChange: (tendencies: TendencyData[]) => void;
}

export function TendencyForm({ tendencies, onChange }: Props) {
  const update = (index: number, field: string, raw: string) => {
    const updated = tendencies.map((t, i) => {
      if (i !== index) return t;
      const num = parseFloat(raw);
      return { ...t, [field]: isNaN(num) ? raw : num };
    });
    onChange(updated);
  };

  const updateType = (index: number, type: TendencyType) => {
    const updated = tendencies.map((t, i) => {
      if (i !== index) return t;
      return { type };
    });
    onChange(updated);
  };

  const remove = (index: number) => {
    onChange(tendencies.filter((_, i) => i !== index));
  };

  const add = () => {
    onChange([...tendencies, { type: "constant", duration: 10, value: 0 }]);
  };

  const renderField = (t: TendencyData, idx: number, field: string) => {
    const val = t[field as keyof TendencyData];
    return (
      <div key={field} className="tendency-row">
        <span className="tendency-label">{field}</span>
        <input
          className="tendency-input"
          type="number"
          step="any"
          value={val !== undefined ? String(val) : ""}
          onChange={(e) => update(idx, field, e.target.value)}
          placeholder={field}
        />
      </div>
    );
  };

  return (
    <div className="tendency-form">
      {tendencies.map((t, idx) => {
        const fields = TENDENCY_FIELDS[t.type] ?? ["duration"];
        return (
          <div key={idx} className="tendency-item">
            <div className="tendency-row" style={{ justifyContent: "space-between" }}>
              <select
                className="tendency-select"
                value={t.type}
                onChange={(e) => updateType(idx, e.target.value as TendencyType)}
              >
                {TENDENCY_TYPES.map((tp) => (
                  <option key={tp} value={tp}>{tp}</option>
                ))}
              </select>
              <button className="tendency-remove" onClick={() => remove(idx)} title="Remove">
                ×
              </button>
            </div>
            {fields.map((f) => renderField(t, idx, f))}
          </div>
        );
      })}
      <button className="tendency-add-btn" onClick={add}>+ Add tendency</button>
    </div>
  );
}
