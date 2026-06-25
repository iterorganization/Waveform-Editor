import { useStore } from "../../store";
import { SvgLineChart } from "./SvgLineChart";

const METRICS = [
  { key: "elongation",    inputKey: "kappa", label: "κ", color: "#4f8ef7" },
  { key: "triangularity", inputKey: "delta", label: "δ", color: "#7c5cfc" },
  { key: "minor_radius",  inputKey: "a",     label: "a", color: "#3ddc84" },
];

export function ShapeMetricsChart() {
  const { results, currentResultIndex, shapePreviewData, shapePreviewIndex } = useStore();
  const times = results.map((r) => r.t);
  const currentTime = shapePreviewData?.times[shapePreviewIndex] ?? results[currentResultIndex]?.t ?? null;

  const series = METRICS.flatMap(({ key, inputKey, label, color }) => [
    { label: `${label} (NICE)`,  color, xs: times, ys: results.map((r) => r.metrics[key] ?? null),             width: 2   },
    { label: `${label} (input)`, color, xs: times, ys: results.map((r) => r.input_values[inputKey] ?? null),  dash: true,    width: 1.5 },
  ]);

  return <SvgLineChart series={series} xLabel="Time [s]" yLabel="Shape param" currentX={currentTime} empty="Run NICE to see shape metrics." />;
}
