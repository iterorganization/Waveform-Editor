import { useStore } from "../store";
import { ComparisonPanel } from "./comparison/ComparisonPanel";
import { EquilibriumPlot } from "./visualization/EquilibriumPlot";
import { MetricsBar } from "./visualization/MetricsBar";
import { PlaybackScrubber } from "./visualization/PlaybackScrubber";

export function RightPanel() {
  const { niceRunning, niceProgress, niceStatus, results } = useStore();

  const progressPct = niceProgress.total
    ? Math.round((niceProgress.current / niceProgress.total) * 100)
    : 0;

  return (
    <div className="right-panel">
      {/* Equilibrium plot fills the upper ~60% */}
      <div style={{ flex: "0 0 60%", minHeight: 0, display: "flex", flexDirection: "column" }}>
        <EquilibriumPlot />
        <MetricsBar />
        <PlaybackScrubber />
      </div>

      {/* Status bar */}
      <div className="status-bar">
        <div
          className={`status-dot ${niceRunning ? "running" : results.length ? "idle" : "idle"}`}
        />
        <span>{niceStatus || (results.length ? `${results.length} timesteps computed` : "Ready")}</span>
        {niceRunning && niceProgress.total > 0 && (
          <>
            <div className="progress-bar-outer">
              <div
                className="progress-bar-inner"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span>{progressPct}%</span>
          </>
        )}
      </div>

      {/* Comparison plots fill the lower ~40% */}
      <div style={{ flex: "0 0 40%", minHeight: 0, overflow: "hidden" }}>
        <ComparisonPanel />
      </div>
    </div>
  );
}
