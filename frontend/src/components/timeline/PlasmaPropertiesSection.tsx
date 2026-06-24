import { useState } from "react";
import { useStore } from "../../store";
import { WaveformLane } from "./WaveformLane";
import type { WaveformSpec } from "../../types";

const PROPERTY_PARAMS = [
  { name: "ip",            label: "Ip — Plasma current [A]",       color: "#4f8ef7" },
  { name: "b0",            label: "B₀ — Toroidal field [T]",       color: "#7c5cfc" },
  { name: "r0",            label: "R₀ — Reference radius [m]",     color: "#3ddc84" },
  { name: "profile_alpha", label: "α — Profile alpha",             color: "#ff8c42" },
  { name: "profile_beta",  label: "β — Profile beta",              color: "#ffca28" },
  { name: "profile_gamma", label: "γ — Profile gamma",             color: "#ff5370" },
];

export function PlasmaPropertiesSection() {
  const [open, setOpen] = useState(true);
  const { parsedConfig } = useStore();

  const loadedNames = new Set(parsedConfig?.waveforms.map((w) => w.name) ?? []);

  return (
    <div className="section">
      <div className="section-header" onClick={() => setOpen(!open)}>
        <span className={`section-chevron ${open ? "open" : ""}`}>▶</span>
        <span className="section-title">Plasma Properties</span>
        <span className="section-badge">
          {PROPERTY_PARAMS.filter((p) => loadedNames.has(p.name)).length}/{PROPERTY_PARAMS.length}
        </span>
      </div>
      {open && (
        <div className="section-body">
          {PROPERTY_PARAMS.map(({ name, label, color }) => (
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
            Define waveforms named <code>ip</code>, <code>b0</code>, <code>r0</code>, etc. in your YAML to configure plasma properties.
          </div>
        </div>
      )}
    </div>
  );
}
