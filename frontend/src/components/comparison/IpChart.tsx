import { useStore } from "../../store";
import { SvgLineChart } from "./SvgLineChart";

export function IpChart() {
  const { results, currentResultIndex, shapePreviewData, shapePreviewIndex } = useStore();
  const times = results.map((r) => r.t);
  const currentTime = shapePreviewData?.times[shapePreviewIndex] ?? results[currentResultIndex]?.t ?? null;

  const series = [
    { label: "Ip actual (NICE)", color: "#4f8ef7", xs: times, ys: results.map((r) => (r.metrics.ip_actual ?? 0) / 1e6), width: 2 },
    { label: "Ip prescribed",    color: "#4f8ef7", xs: times, ys: results.map((r) => (r.input_values.ip ?? 0) / 1e6),   dash: true,    width: 1.5 },
  ];

  return <SvgLineChart series={series} xLabel="Time [s]" yLabel="Ip [MA]" currentX={currentTime} empty="Run NICE to see Ip waveform." />;
}
