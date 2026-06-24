import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data as PlotlyData, Layout as PlotlyLayout } from "plotly.js";
import { useStore } from "../../store";

export function ProfilesChart() {
  const { results, currentResultIndex } = useStore();
  const result = results[currentResultIndex];

  const { traces, layout } = useMemo(() => {
    if (!result) return { traces: [], layout: {} };

    const ts: PlotlyData[] = [];

    // Output profiles
    if (result.psi_norm.length) {
      ts.push({
        x: result.psi_norm, y: result.dpressure_dpsi,
        mode: "lines", name: "dp/dψ (NICE output)",
        line: { color: "#4f8ef7", width: 2 },
        type: "scatter",
      });
      ts.push({
        x: result.psi_norm, y: result.f_df_dpsi,
        mode: "lines", name: "fdf/dψ (NICE output)",
        line: { color: "#7c5cfc", width: 2 },
        type: "scatter",
      });
    }

    // Input profiles
    if (result.input_psi_norm.length) {
      ts.push({
        x: result.input_psi_norm, y: result.input_dpressure_dpsi,
        mode: "lines", name: "dp/dψ (prescribed)",
        line: { color: "#4f8ef7", width: 1.5, dash: "dash" },
        type: "scatter",
      });
      ts.push({
        x: result.input_psi_norm, y: result.input_f_df_dpsi,
        mode: "lines", name: "fdf/dψ (prescribed)",
        line: { color: "#7c5cfc", width: 1.5, dash: "dash" },
        type: "scatter",
      });
    }

    const layout: Partial<PlotlyLayout> = {
      paper_bgcolor: "var(--bg2)", plot_bgcolor: "var(--bg)",
      font: { color: "#e2e4f0", size: 11 },
      xaxis: {
        title: { text: "ψ_norm" }, color: "#7c84a8",
        gridcolor: "#242740", zeroline: false, range: [0, 1],
      },
      yaxis: { title: { text: "Profile value [A.U.]" }, color: "#7c84a8", gridcolor: "#242740" },
      margin: { l: 65, r: 10, t: 30, b: 40 },
      title: {
        text: result ? `Profiles at t = ${result.t.toFixed(2)} s` : "Profiles",
        font: { size: 12 }, x: 0.5,
      },
      legend: { bgcolor: "rgba(0,0,0,0)", font: { size: 10 } },
    };

    return { traces: ts, layout };
  }, [result]);

  if (!result) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                    height: "100%", color: "var(--text-muted)", fontSize: 12 }}>
        Run NICE to see profiles. Use the scrubber to select a timestep.
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
