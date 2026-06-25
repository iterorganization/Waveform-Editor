import { useStore } from "../../store";
import { CHART_COLORS, SvgLineChart } from "./SvgLineChart";

export function CoilCurrentsChart() {
  const { results, currentResultIndex, shapePreviewData, shapePreviewIndex } = useStore();
  const times = results.map((r) => r.t);
  const currentTime = shapePreviewData?.times[shapePreviewIndex] ?? results[currentResultIndex]?.t ?? null;
  const coilNames = results[0]?.coil_names ?? [];

  const series = coilNames.map((name, i) => ({
    label: name,
    color: CHART_COLORS[i % CHART_COLORS.length],
    xs: times,
    ys: results.map((r) => r.coil_currents[i] ?? null),
    width: 1.5,
  }));

  return <SvgLineChart series={series} xLabel="Time [s]" yLabel="Current [A]" currentX={currentTime} empty="Run NICE to see coil currents." />;
}
