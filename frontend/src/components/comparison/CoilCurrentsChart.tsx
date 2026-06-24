import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data as PlotlyData, Layout as PlotlyLayout } from "plotly.js";
import { useStore } from "../../store";

const COLORS = [
  "#4f8ef7", "#7c5cfc", "#3ddc84", "#ff8c42",
  "#ffca28", "#ff5370", "#f06292", "#26c6da",
  "#ab47bc", "#66bb6a", "#ffa726", "#ec407a",
];

export function CoilCurrentsChart() {
  const { results } = useStore();

  const { traces, layout } = useMemo(() => {
    if (!results.length) return { traces: [], layout: {} };

    const times = results.map((r) => r.t);

    // Collect all unique coil names
    const coilNames = results[0]?.coil_names ?? [];

    const ts: PlotlyData[] = coilNames.map((name, i) => ({
      x: times,
      y: results.map((r) => r.coil_currents[i] ?? null),
      mode: "lines+markers",
      name,
      line: { color: COLORS[i % COLORS.length], width: 1.5 },
      marker: { size: 3 },
      type: "scatter",
    }));

    const layout: Partial<PlotlyLayout> = {
      paper_bgcolor: "var(--bg2)", plot_bgcolor: "var(--bg)",
      font: { color: "#e2e4f0", size: 11 },
      xaxis: { title: { text: "Time [s]" }, color: "#7c84a8", gridcolor: "#242740", zeroline: false },
      yaxis: { title: { text: "Coil current [A]" }, color: "#7c84a8", gridcolor: "#242740" },
      margin: { l: 65, r: 10, t: 24, b: 40 },
      legend: { bgcolor: "rgba(0,0,0,0)", font: { size: 9 } },
      hovermode: "x unified",
    };

    return { traces: ts, layout };
  }, [results]);

  if (!results.length || !results[0]?.coil_names.length) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                    height: "100%", color: "var(--text-muted)", fontSize: 12 }}>
        Run NICE to see coil current waveforms.
      </div>
    );
  }

  return (
    <Plot
      data={traces}
      layout={layout}
      config={{ responsive: true, displayModeBar: false }}
      style={{ width: "100%", height: "100%" }}
      useResizeHandler
    />
  );
}
