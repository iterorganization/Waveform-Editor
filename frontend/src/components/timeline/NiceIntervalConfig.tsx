import { useState } from "react";
import { useStore } from "../../store";

export function NiceIntervalConfig() {
  const [open, setOpen] = useState(true);
  const [extraInput, setExtraInput] = useState("");
  const { niceInterval, setNiceInterval, parsedConfig } = useStore();

  const tStart = parsedConfig?.time_start ?? 0;
  const tEnd = parsedConfig?.time_end ?? 100;

  const addExtra = () => {
    const v = parseFloat(extraInput);
    if (!isNaN(v)) {
      setNiceInterval({
        extraTimesteps: [...niceInterval.extraTimesteps, v].sort((a, b) => a - b),
      });
      setExtraInput("");
    }
  };

  const removeExtra = (t: number) => {
    setNiceInterval({
      extraTimesteps: niceInterval.extraTimesteps.filter((x) => x !== t),
    });
  };

  // Compute all timesteps for the preview bar
  const range = tEnd - tStart || 1;
  const uniformTs: number[] = [];
  for (let t = tStart; t <= tEnd + 1e-9; t += niceInterval.uniformStep) {
    uniformTs.push(parseFloat(t.toFixed(6)));
  }
  const allTs = Array.from(
    new Set([...uniformTs, ...niceInterval.extraTimesteps]),
  ).sort((a, b) => a - b);

  return (
    <div className="section">
      <div className="section-header" onClick={() => setOpen(!open)}>
        <span className={`section-chevron ${open ? "open" : ""}`}>▶</span>
        <span className="section-title">NICE Run Intervals</span>
        <span className="section-badge">{allTs.length} timesteps</span>
      </div>
      {open && (
        <div className="nice-interval">
          <div className="nice-interval-row">
            <span className="nice-interval-label">Uniform step (s)</span>
            <input
              type="number"
              min={0.1}
              step={0.5}
              value={niceInterval.uniformStep}
              onChange={(e) =>
                setNiceInterval({ uniformStep: parseFloat(e.target.value) || 1 })
              }
            />
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              t: {tStart.toFixed(1)} → {tEnd.toFixed(1)} s
            </span>
          </div>

          <div className="nice-interval-row" style={{ alignItems: "flex-start" }}>
            <span className="nice-interval-label">Extra times (s)</span>
            <div style={{ flex: 1 }}>
              <div className="extra-ts-chips">
                {niceInterval.extraTimesteps.map((t) => (
                  <span key={t} className="ts-chip">
                    {t}s
                    <button className="ts-chip-remove" onClick={() => removeExtra(t)}>×</button>
                  </span>
                ))}
                <div style={{ display: "flex", gap: 4 }}>
                  <input
                    type="number"
                    step="any"
                    value={extraInput}
                    onChange={(e) => setExtraInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addExtra()}
                    placeholder="t =…"
                    style={{ width: 70, padding: "2px 6px", background: "var(--bg3)",
                             border: "1px solid var(--border)", borderRadius: 4,
                             color: "var(--text)", outline: "none" }}
                  />
                  <button className="btn btn-sm" onClick={addExtra}>+</button>
                </div>
              </div>
            </div>
          </div>

          {/* Preview bar */}
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
              Run preview ({allTs.length} runs):
            </div>
            <div className="timestep-preview">
              {allTs.map((t) => (
                <div
                  key={t}
                  className="timestep-mark"
                  style={{ left: `${((t - tStart) / range) * 100}%` }}
                  title={`t = ${t}s`}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
