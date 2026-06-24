import { useState } from "react";
import { useStore } from "../../store";
import { WaveformLane } from "./WaveformLane";

const SHAPE_PARAMS = [
  { name: "kappa",    label: "κ — Elongation",         color: "#4f8ef7" },
  { name: "delta",    label: "δ — Triangularity",       color: "#7c5cfc" },
  { name: "a",        label: "a — Minor radius [m]",    color: "#3ddc84" },
  { name: "center_r", label: "R₀ — Center radius [m]",  color: "#ff8c42" },
  { name: "center_z", label: "Z₀ — Center height [m]",  color: "#ffca28" },
  { name: "rx",       label: "Rₓ — X-point radius [m]", color: "#ff5370" },
  { name: "zx",       label: "Zₓ — X-point height [m]", color: "#f06292" },
];

export function PlasmaShapeSection() {
  const [open, setOpen] = useState(true);
  const parsedConfig = useStore((s) => s.parsedConfig);
  const loadedNames = new Set(parsedConfig?.waveforms.map((w) => w.name) ?? []);

  return (
    <div className="section">
      <div className="section-header" onClick={() => setOpen(!open)}>
        <span className={`section-chevron ${open ? "open" : ""}`}>▶</span>
        <span className="section-title">Plasma Shape (NICE Inverse)</span>
        <span className="section-badge">
          {SHAPE_PARAMS.filter((p) => loadedNames.has(p.name)).length}/{SHAPE_PARAMS.length}
        </span>
      </div>
      {open && (
        <div className="section-body">
          {SHAPE_PARAMS.map(({ name, label, color }) => (
            loadedNames.has(name) ? (
              <WaveformLane key={name} name={name} spec={[]} color={color} />
            ) : (
              <div key={name} className="waveform-lane" style={{ opacity: 0.45 }}>
                <span className="lane-name" style={{ color: "var(--text-muted)" }}>{label}</span>
                <span className="lane-chip">not defined</span>
              </div>
            )
          ))}
          <div style={{ padding: "6px 12px 6px 20px", fontSize: 11, color: "var(--text-muted)" }}>
            Define waveforms named <code>kappa</code>, <code>delta</code>, <code>a</code>, etc. in your YAML under
            a group (e.g. <code>NICE Shape:</code>) to configure shape.
          </div>
        </div>
      )}
    </div>
  );
}

