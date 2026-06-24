import { useMemo } from "react";

interface Props {
  times: number[];
  values: number[];
  width?: number;
  height?: number;
  color?: string;
}

export function Sparkline({ times, values, width = 80, height = 22, color = "#4f8ef7" }: Props) {
  const path = useMemo(() => {
    if (!times.length || !values.length) return null;
    const minT = times[0], maxT = times[times.length - 1];
    const minV = Math.min(...values);
    const maxV = Math.max(...values);
    const rangeT = maxT - minT || 1;
    const rangeV = maxV - minV || 1;
    const pad = 2;
    const w = width - pad * 2;
    const h = height - pad * 2;

    const pts = times.map((t, i) => {
      const x = pad + ((t - minT) / rangeT) * w;
      const y = pad + h - ((values[i] - minV) / rangeV) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return pts.join(" ");
  }, [times, values, width, height]);

  if (!path) {
    return (
      <svg width={width} height={height} className="sparkline-svg">
        <line x1={2} y1={height / 2} x2={width - 2} y2={height / 2}
              stroke="var(--border)" strokeWidth={1} strokeDasharray="3,2" />
      </svg>
    );
  }

  return (
    <svg width={width} height={height} className="sparkline-svg">
      <polyline points={path} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}
