import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data as PlotlyData, Layout as PlotlyLayout } from "plotly.js";
import { useStore } from "../../store";
import type { MachineGeometries, TimestepResult } from "../../types";

// Miller parameterization: R(θ)=R0+a·cos(θ+arcsin(δ)·sin(θ)), Z(θ)=Z0+κ·a·sin(θ)
function millerOutline(kappa: number, delta: number, a: number, R0: number, Z0: number, n = 100) {
  const da = Math.asin(Math.min(1, Math.max(-1, delta)));
  const R: number[] = [];
  const Z: number[] = [];
  for (let i = 0; i <= n; i++) {
    const th = (2 * Math.PI * i) / n;
    R.push(R0 + a * Math.cos(th + da * Math.sin(th)));
    Z.push(Z0 + kappa * a * Math.sin(th));
  }
  return { R, Z };
}

function machineTraces(geo: MachineGeometries) {
  const traces: PlotlyData[] = [];

  // Vacuum vessel
  for (const u of geo.vacuum_vessel) {
    traces.push({
      x: u.r, y: u.z, mode: "lines", type: "scatter",
      line: { color: "#555", width: 1 },
      name: u.name, showlegend: false, hovertemplate: `%{text}<extra></extra>`,
      text: Array(u.r.length).fill(u.name),
    });
  }

  // Wall/limiter
  for (const u of geo.wall_limiter) {
    traces.push({
      x: u.r, y: u.z, mode: "lines", type: "scatter",
      line: { color: "#888", width: 1.5 },
      name: u.name, showlegend: false, hovertemplate: `%{text}<extra></extra>`,
      text: Array(u.r.length).fill(u.name),
    });
  }

  // Coil rectangles
  for (const c of geo.coil_rectangles) {
    const r = [c.r0, c.r1, c.r1, c.r0, c.r0];
    const z = [c.z0, c.z0, c.z1, c.z1, c.z0];
    traces.push({
      x: r, y: z, mode: "lines", type: "scatter",
      line: { color: "#aaa", width: 1.5 },
      name: c.name, showlegend: false, hovertemplate: `%{text}<extra></extra>`,
      text: Array(5).fill(c.name),
    });
  }

  // Coil paths
  for (const c of geo.coil_paths) {
    traces.push({
      x: c.r, y: c.z, mode: "lines", type: "scatter",
      line: { color: "#aaa", width: 1.5 },
      name: c.name, showlegend: false,
    });
  }

  return traces;
}

function equilibriumTraces(result: TimestepResult): PlotlyData[] {
  const traces: PlotlyData[] = [];

  // Flux contours (colored by psi value)
  if (result.contours.length) {
    const psiValues = result.contours.map((c) => c.psi);
    const minPsi = Math.min(...psiValues);
    const maxPsi = Math.max(...psiValues);
    const range = maxPsi - minPsi || 1;

    for (const seg of result.contours) {
      const norm = (seg.psi - minPsi) / range;
      // Viridis-like color interpolation
      const r = Math.round(68 + norm * (253 - 68));
      const g = Math.round(1 + norm * (231 - 1));
      const b = Math.round(84 + norm * (37 - 84));
      traces.push({
        x: seg.x, y: seg.y, mode: "lines", type: "scatter",
        line: { color: `rgb(${r},${g},${b})`, width: 0.8 },
        showlegend: false,
        hovertemplate: `ψ = ${seg.psi.toFixed(4)}<extra></extra>`,
      });
    }
  }

  // Separatrix
  if (result.separatrix_r.length) {
    const r = [...result.separatrix_r, result.separatrix_r[0]];
    const z = [...result.separatrix_z, result.separatrix_z[0]];
    traces.push({
      x: r, y: z, mode: "lines", type: "scatter",
      line: { color: "#ff5370", width: 2.5 },
      name: "Separatrix", showlegend: false,
    });
  }

  // O-points
  if (result.o_points.length) {
    traces.push({
      x: result.o_points.map((p) => p.r),
      y: result.o_points.map((p) => p.z),
      mode: "markers", type: "scatter",
      marker: { symbol: "circle", size: 8, color: "#fff", line: { color: "#000", width: 1.5 } },
      name: "O-point", showlegend: false,
      hovertemplate: "O-point<extra></extra>",
    });
  }

  // X-points
  if (result.x_points.length) {
    traces.push({
      x: result.x_points.map((p) => p.r),
      y: result.x_points.map((p) => p.z),
      mode: "markers", type: "scatter",
      marker: { symbol: "x", size: 10, color: "#fff", line: { color: "#000", width: 2 } },
      name: "X-point", showlegend: false,
      hovertemplate: "X-point<extra></extra>",
    });
  }

  return traces;
}

export function EquilibriumPlot() {
  const {
    machineGeometries, results, currentResultIndex,
    shapePreviewData, shapePreviewIndex,
  } = useStore();
  const currentResult = results[currentResultIndex] ?? null;

  // When NICE results are shown, align the analytical outline to the result's time.
  const shapeIdx = useMemo(() => {
    if (results.length > 0 && shapePreviewData) {
      const target = currentResult?.t ?? 0;
      let best = 0;
      let bestDist = Infinity;
      for (let i = 0; i < shapePreviewData.times.length; i++) {
        const d = Math.abs(shapePreviewData.times[i] - target);
        if (d < bestDist) { bestDist = d; best = i; }
      }
      return best;
    }
    return shapePreviewIndex;
  }, [results, currentResult, shapePreviewData, shapePreviewIndex]);

  const traces = useMemo(() => {
    const t: PlotlyData[] = [];
    if (machineGeometries) t.push(...machineTraces(machineGeometries));
    if (currentResult?.status === "success") t.push(...equilibriumTraces(currentResult));

    // Analytical input shape drawn from waveform values at the current time
    if (shapePreviewData) {
      const wf = shapePreviewData.waveforms;
      if (wf.kappa && wf.a && wf.center_r) {
        const kappa = wf.kappa[shapeIdx] ?? 1;
        const delta = wf.delta?.[shapeIdx] ?? 0;
        const a = wf.a[shapeIdx] ?? 1;
        const R0 = wf.center_r[shapeIdx] ?? 6.2;
        const Z0 = wf.center_z?.[shapeIdx] ?? 0;
        const { R, Z } = millerOutline(kappa, delta, a, R0, Z0);
        t.push({
          x: R, y: Z, mode: "lines", type: "scatter",
          line: { color: "#00e5ff", width: 2 },
          name: "Input shape", showlegend: false,
          hovertemplate: `Input shape — t = ${shapePreviewData.times[shapeIdx].toFixed(2)} s<extra></extra>`,
        });
      }
    }

    return t;
  }, [machineGeometries, currentResult, shapePreviewData, shapeIdx]);

  const displayTime = currentResult
    ? currentResult.t
    : shapePreviewData?.times[shapePreviewIndex] ?? null;

  const layout: Partial<PlotlyLayout> = {
    paper_bgcolor: "var(--bg)",
    plot_bgcolor: "var(--bg)",
    font: { color: "#e2e4f0", size: 11 },
    xaxis: {
      title: { text: "R [m]", standoff: 4 },
      color: "#7c84a8", gridcolor: "#242740", zeroline: false,
      range: [0, 13],
    },
    yaxis: {
      title: { text: "Z [m]", standoff: 4 },
      color: "#7c84a8", gridcolor: "#242740", zeroline: false,
      scaleanchor: "x", scaleratio: 1,
      range: [-10, 10],
    },
    margin: { l: 50, r: 16, t: 30, b: 40 },
    title: {
      text: displayTime !== null
        ? `Equilibrium — t = ${displayTime.toFixed(2)} s`
        : "Equilibrium",
      font: { size: 13 },
      x: 0.5,
    },
    showlegend: false,
    hovermode: "closest",
    uirevision: "fixed",
  };

  return (
    <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
      <Plot
        data={traces}
        layout={layout}
        config={{ responsive: true, displayModeBar: true, displaylogo: false }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
      {!machineGeometries && !currentResult && !shapePreviewData && (
        <div
          style={{
            position: "absolute", inset: 0, display: "flex", alignItems: "center",
            justifyContent: "center", color: "var(--text-muted)", fontSize: 13,
            pointerEvents: "none",
          }}
        >
          Configure machine description in Settings, then run NICE.
        </div>
      )}
    </div>
  );
}
