import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data as PlotlyData, Layout as PlotlyLayout } from "plotly.js";
import { useStore } from "../../store";

const OUTPUT_METRICS = [
  { key: "elongation",          label: "κ (output)",  color: "#4f8ef7" },
  { key: "triangularity",       label: "δ (output)",  color: "#7c5cfc" },
  { key: "minor_radius",        label: "a (output)",  color: "#3ddc84" },
];

const INPUT_MAP: Record<string, string> = {
  elongation:    "kappa",
  triangularity: "delta",
  minor_radius:  "a",
};

export function ShapeMetricsChart() {
  const { results } = useStore();

  const { traces, layout } = useMemo(() => {
    const ts: PlotlyData[] = [];
    const times = results.map((r) => r.t);

    for (const { key, label, color } of OUTPUT_METRICS) {
      const vals = results.map((r) => r.metrics[key] ?? null);
      ts.push({
        x: times, y: vals, mode: "lines+markers",
        name: label, line: { color, width: 2 },
        marker: { size: 4 },
        type: "scatter",
      });
    }

    // Input waveforms (from input_values stored in results)
    for (const { key, color } of OUTPUT_METRICS) {
      const inputKey = INPUT_MAP[key];
      if (!inputKey) continue;
      const vals = results.map((r) => r.input_values[inputKey] ?? null);
      if (vals.some((v) => v !== null)) {
        ts.push({
          x: times, y: vals, mode: "lines",
          name: `${inputKey} (input)`,
          line: { color, width: 1.5, dash: "dash" },
          type: "scatter",
        });
      }
    }

    const layout: Partial<PlotlyLayout> = {
      paper_bgcolor: "var(--bg2)", plot_bgcolor: "var(--bg)",
      font: { color: "#e2e4f0", size: 11 },
      xaxis: { title: { text: "Time [s]" }, color: "#7c84a8", gridcolor: "#242740", zeroline: false },
      yaxis: { title: { text: "Shape parameter" }, color: "#7c84a8", gridcolor: "#242740" },
      margin: { l: 55, r: 10, t: 24, b: 40 },
      legend: { bgcolor: "rgba(0,0,0,0)", font: { size: 10 } },
      hovermode: "x unified",
    };

    return { traces: ts, layout };
  }, [results]);

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
