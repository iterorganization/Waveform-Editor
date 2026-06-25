import { useStore } from "../../store";
import { SvgLineChart } from "./SvgLineChart";

export function ProfilesChart() {
  const { results, currentResultIndex } = useStore();
  const result = results[currentResultIndex];

  const series = result ? [
    { label: "dp/dψ (NICE)",   color: "#4f8ef7", xs: result.psi_norm,       ys: result.dpressure_dpsi,       width: 2 },
    { label: "fdf/dψ (NICE)",  color: "#7c5cfc", xs: result.psi_norm,       ys: result.f_df_dpsi,            width: 2 },
    { label: "dp/dψ (input)",  color: "#4f8ef7", xs: result.input_psi_norm, ys: result.input_dpressure_dpsi, dash: true, width: 1.5 },
    { label: "fdf/dψ (input)", color: "#7c5cfc", xs: result.input_psi_norm, ys: result.input_f_df_dpsi,      dash: true, width: 1.5 },
  ] : [];

  return (
    <SvgLineChart
      series={series}
      xLabel="ψ_norm"
      yLabel="Profile [A.U.]"
      title={result ? `NICE result at t = ${result.t.toFixed(2)} s` : undefined}
      empty={results.length
        ? "No NICE result at or before this time — scrub forward."
        : "Run NICE to see profiles. Use the scrubber to select a timestep."}
    />
  );
}
