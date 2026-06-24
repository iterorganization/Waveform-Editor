import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data as PlotlyData, Layout as PlotlyLayout } from "plotly.js";
import { useStore } from "../../store";

export function IpChart() {
  const { results } = useStore();

  const { traces, layout } = useMemo(() => {
    const times = results.map((r) => r.t);
    const ipActual = results.map((r) => (r.metrics.ip_actual ?? 0) / 1e6);
    const ipInput = results.map((r) => (r.input_values.ip ?? 0) / 1e6);

    const ts: PlotlyData[] = [
      {
        x: times, y: ipActual, mode: "lines+markers",
        name: "Ip actual (NICE)",
        line: { color: "#4f8ef7", width: 2 },
        marker: { size: 4 },
        type: "scatter",
      },
      {
        x: times, y: ipInput, mode: "lines",
        name: "Ip prescribed",
        line: { color: "#4f8ef7", width: 1.5, dash: "dash" },
        type: "scatter",
      },
    ];

    const layout: Partial<PlotlyLayout> = {
      paper_bgcolor: "var(--bg2)", plot_bgcolor: "var(--bg)",
      font: { color: "#e2e4f0", size: 11 },
      xaxis: { title: { text: "Time [s]" }, color: "#7c84a8", gridcolor: "#242740", zeroline: false },
      yaxis: { title: { text: "Ip [MA]" }, color: "#7c84a8", gridcolor: "#242740" },
      margin: { l: 60, r: 10, t: 24, b: 40 },
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
