import { useStore } from "../../store";

const METRICS = [
  { key: "elongation",          sym: "κ",    unit: "",  label: "Elongation" },
  { key: "triangularity",       sym: "δ",    unit: "",  label: "Triangularity" },
  { key: "triangularity_upper", sym: "δᵤ",   unit: "",  label: "Tri upper" },
  { key: "triangularity_lower", sym: "δₗ",   unit: "",  label: "Tri lower" },
  { key: "q95",                 sym: "q₉₅",  unit: "",  label: "Safety factor at 95%" },
  { key: "major_radius",        sym: "R₀",   unit: "m", label: "Major radius" },
  { key: "minor_radius",        sym: "a",    unit: "m", label: "Minor radius" },
  { key: "vertical_position",   sym: "Z₀",   unit: "m", label: "Vertical position" },
  { key: "ip_actual",           sym: "Ip",   unit: "A", label: "Plasma current (actual)" },
];

export function MetricsBar() {
  const { results, currentResultIndex } = useStore();
  const result = results[currentResultIndex];
  const metrics = result?.metrics ?? {};

  return (
    <div className="metrics-bar">
      {METRICS.map(({ key, sym, unit, label }) => {
        const raw = metrics[key];
        const display =
          raw !== undefined
            ? unit === "A"
              ? `${(raw / 1e6).toFixed(2)} MA`
              : `${raw.toFixed(3)} ${unit}`.trim()
            : "—";
        return (
          <div key={key} className="metric-chip" title={label}>
            <span className="mc-sym">{sym}</span>
            <span className="mc-val">{display}</span>
          </div>
        );
      })}
    </div>
  );
}
