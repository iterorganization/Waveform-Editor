import { useEffect, useRef, useState } from "react";

// ── Shared helpers (same logic as WaveformPlot) ────────────────────────────────

const PAD = { top: 24, right: 16, bottom: 40, left: 66 };

export const CHART_COLORS = [
  "#4f8ef7", "#7c5cfc", "#3ddc84", "#ff8c42",
  "#ffca28", "#ff5370", "#f06292", "#26c6da",
  "#ab47bc", "#66bb6a", "#ffa726", "#ec407a",
];

function niceTickValues(min: number, max: number, count: number): number[] {
  if (!isFinite(min) || !isFinite(max) || min >= max) return isFinite(min) ? [min] : [];
  const range = max - min;
  // Below float resolution: a step this small cannot advance the loop (v += step === v)
  if (range < (Math.abs(min) + Math.abs(max)) * 1e-12) return [min];
  const raw = range / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = norm < 1.5 ? mag : norm < 3.5 ? 2 * mag : norm < 7.5 ? 5 * mag : 10 * mag;
  if (!(step > 0)) return [min, max];
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 0.01 && ticks.length < 500; v += step)
    ticks.push(parseFloat(v.toPrecision(10)));
  return ticks;
}

function fmtVal(v: number): string {
  const abs = Math.abs(v);
  if (abs === 0) return "0";
  if (abs >= 1e6 || (abs < 1e-3 && abs > 0)) return v.toExponential(2);
  if (abs >= 100) return v.toFixed(1);
  if (abs >= 10)  return v.toFixed(2);
  return v.toFixed(3);
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ChartSeries {
  label: string;
  color?: string;
  xs: number[];
  ys: (number | null)[];
  dash?: boolean;
  markers?: boolean;
  width?: number;
}

interface Props {
  series: ChartSeries[];
  xLabel?: string;
  yLabel?: string;
  title?: string;
  /** Vertical cursor line at this x value (e.g. current time) */
  currentX?: number | null;
  /** Message shown when series is empty */
  empty?: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function SvgLineChart({ series, xLabel, yLabel, title, currentX, empty }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 600, h: 300 });
  const [viewRange, setViewRange] = useState<{ xMin: number; xMax: number; yMin: number; yMax: number } | null>(null);
  const [panState, setPanState] = useState<{ sx: number; sy: number; sv: typeof viewRange } | null>(null);
  const wheelRef = useRef<((e: WheelEvent) => void) | null>(null);

  useEffect(() => {
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setSize({ w: width, h: height });
    });
    if (containerRef.current) obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const h = (e: WheelEvent) => wheelRef.current?.(e);
    svg.addEventListener("wheel", h, { passive: false });
    return () => svg.removeEventListener("wheel", h);
  }, []);

  const { w, h } = size;
  const plotW = w - PAD.left - PAD.right;
  const plotH = h - PAD.top - PAD.bottom;

  // Compute data bounds across all series
  const allXs = series.flatMap((s) => s.xs.filter((v) => Number.isFinite(v)));
  const allYs = series.flatMap((s) => s.ys.filter((v): v is number => Number.isFinite(v)));

  const rawXMin = allXs.length ? Math.min(...allXs) : 0;
  const rawXMax = allXs.length ? Math.max(...allXs) : 1;
  const rawYMin = allYs.length ? Math.min(...allYs) : -1;
  const rawYMax = allYs.length ? Math.max(...allYs) : 1;

  // Spans below float resolution (e.g. NICE ip converging to prescribed ip within
  // ~1e-15 relative) must be treated as flat, or the view range degenerates.
  const xFlat = (rawXMax - rawXMin) < (Math.abs(rawXMin) + Math.abs(rawXMax)) * 1e-12;
  const yFlat = (rawYMax - rawYMin) < (Math.abs(rawYMin) + Math.abs(rawYMax)) * 1e-12;
  const xPad = xFlat ? Math.max(Math.abs(rawXMax) * 0.05, 0.5) : (rawXMax - rawXMin) * 0.04;
  const yPad = yFlat ? Math.max(Math.abs(rawYMax) * 0.05, 0.1) : (rawYMax - rawYMin) * 0.12;
  const dataXMin = rawXMin - xPad, dataXMax = rawXMax + xPad;
  const dataYMin = rawYMin - yPad, dataYMax = rawYMax + yPad;

  const xMin = viewRange?.xMin ?? dataXMin;
  const xMax = viewRange?.xMax ?? dataXMax;
  const yMin = viewRange?.yMin ?? dataYMin;
  const yMax = viewRange?.yMax ?? dataYMax;

  const toSvgX = (x: number) => PAD.left + ((x - xMin) / (xMax - xMin || 1)) * plotW;
  const toSvgY = (y: number) => PAD.top + (1 - (y - yMin) / (yMax - yMin || 1)) * plotH;
  const fromSvgX = (sx: number) => xMin + ((sx - PAD.left) / (plotW || 1)) * (xMax - xMin);
  const fromSvgY = (sy: number) => yMin + (1 - (sy - PAD.top) / (plotH || 1)) * (yMax - yMin);

  wheelRef.current = (e: WheelEvent) => {
    e.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (w / rect.width);
    const mouseX = fromSvgX(mx);
    const factor = e.deltaY > 0 ? 1.15 : 1 / 1.15;
    const newXMin = mouseX - (mouseX - xMin) * factor;
    const newXMax = mouseX + (xMax - mouseX) * factor;
    if (newXMax - newXMin < 1e-9) return;
    setViewRange({ xMin: newXMin, xMax: newXMax, yMin, yMax });
  };

  useEffect(() => {
    if (!panState) return;
    const onMove = (e: MouseEvent) => {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const dx = (e.clientX - panState.sx) * (w / rect.width);
      const dy = (e.clientY - panState.sy) * (h / rect.height);
      const sv = panState.sv ?? { xMin: dataXMin, xMax: dataXMax, yMin: dataYMin, yMax: dataYMax };
      const dxData = (sv.xMax - sv.xMin) / plotW;
      const dyData = (sv.yMax - sv.yMin) / plotH;
      setViewRange({ xMin: sv.xMin - dx * dxData, xMax: sv.xMax - dx * dxData, yMin: sv.yMin + dy * dyData, yMax: sv.yMax + dy * dyData });
    };
    const onUp = () => setPanState(null);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [panState, w, h, plotW, plotH, dataXMin, dataXMax, dataYMin, dataYMax]);

  const xTicks = niceTickValues(xMin, xMax, Math.max(3, Math.floor(plotW / 80)));
  const yTicks = niceTickValues(yMin, yMax, Math.max(3, Math.floor(plotH / 48)));

  const showEmpty = !series.length || !allXs.length || plotW <= 0 || plotH <= 0;

  // Legend — only if more than one series or if series have labels
  const legendItems = series.filter((s) => s.label);
  const legendLineH = 16;
  const legendH = legendItems.length * legendLineH + 8;
  const legendW = Math.min(140, Math.max(...legendItems.map((s) => s.label.length * 6.5 + 26)));
  const legendX = PAD.left + plotW - legendW - 4;
  const legendY = PAD.top + 4;

  return (
    <div ref={containerRef} style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
    {showEmpty ? (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-muted)", fontSize: 12 }}>
        {(!series.length || !allXs.length) ? (empty ?? "No data") : "…"}
      </div>
    ) : (
    <svg
      ref={svgRef}
      width={w}
      height={h}
      style={{ display: "block", userSelect: "none", cursor: panState ? "grabbing" : "default" }}
      onDoubleClick={() => setViewRange(null)}
      onMouseDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        setPanState({ sx: e.clientX, sy: e.clientY, sv: viewRange });
      }}
    >
      <defs>
        <clipPath id={`cc-clip-${title}`}>
          <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} />
        </clipPath>
      </defs>

      {/* Background */}
      <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} fill="var(--bg)" rx={2} style={{ cursor: "grab" }} />

      {/* Y grid + labels */}
      {yTicks.map((v) => {
        const y = toSvgY(v);
        if (y < PAD.top - 1 || y > PAD.top + plotH + 1) return null;
        return (
          <g key={`yg${v}`}>
            <line x1={PAD.left} y1={y} x2={PAD.left + plotW} y2={y} stroke="var(--border)" strokeWidth={1} strokeDasharray="3 4" opacity={0.55} />
            <text x={PAD.left - 5} y={y + 4} textAnchor="end" fontSize={9} fill="var(--text-muted)" fontFamily="monospace">{fmtVal(v)}</text>
          </g>
        );
      })}

      {/* X grid + labels */}
      {xTicks.map((x) => {
        const sx = toSvgX(x);
        if (sx < PAD.left - 1 || sx > PAD.left + plotW + 1) return null;
        return (
          <g key={`xg${x}`}>
            <line x1={sx} y1={PAD.top} x2={sx} y2={PAD.top + plotH} stroke="var(--border)" strokeWidth={1} strokeDasharray="3 4" opacity={0.55} />
            <text x={sx} y={PAD.top + plotH + 14} textAnchor="middle" fontSize={9} fill="var(--text-muted)" fontFamily="monospace">{fmtVal(x)}</text>
          </g>
        );
      })}

      {/* Axis border */}
      <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} fill="none" stroke="var(--border)" strokeWidth={1} />

      {/* Axis labels */}
      {xLabel && <text x={PAD.left + plotW / 2} y={h - 4} textAnchor="middle" fontSize={10} fill="var(--text-muted)">{xLabel}</text>}
      {yLabel && (
        <text x={12} y={PAD.top + plotH / 2} textAnchor="middle" fontSize={10} fill="var(--text-muted)"
          transform={`rotate(-90,12,${PAD.top + plotH / 2})`}>{yLabel}</text>
      )}
      {title && <text x={PAD.left + plotW / 2} y={14} textAnchor="middle" fontSize={10} fill="var(--text-muted)" fontWeight={500}>{title}</text>}

      {/* Series lines */}
      <g clipPath={`url(#cc-clip-${title})`}>
        {series.map((s, si) => {
          const color = s.color ?? CHART_COLORS[si % CHART_COLORS.length];
          const width = s.width ?? 1.8;
          // Build path, breaking on nulls
          let d = "";
          let pen = false; // false → next point starts a new subpath
          let pointCount = 0;
          for (let i = 0; i < s.xs.length; i++) {
            const y = s.ys[i];
            if (y === null || !isFinite(y)) { pen = false; continue; }
            const sx = toSvgX(s.xs[i]), sy = toSvgY(y);
            d += `${pen ? "L" : "M"} ${sx} ${sy} `;
            pen = true;
            pointCount++;
          }
          // A single point strokes nothing — fall back to markers so it stays visible
          const showMarkers = s.markers || pointCount === 1;
          return (
            <g key={si}>
              <path d={d} fill="none" stroke={color} strokeWidth={width}
                strokeDasharray={s.dash ? "6 3" : undefined} />
              {showMarkers && s.xs.map((x, i) => {
                const y = s.ys[i];
                if (y === null || !isFinite(y)) return null;
                return <circle key={i} cx={toSvgX(x)} cy={toSvgY(y)} r={2.5} fill={color} />;
              })}
            </g>
          );
        })}

        {/* Current-X cursor */}
        {currentX !== null && currentX !== undefined && (() => {
          const sx = toSvgX(currentX);
          if (sx < PAD.left || sx > PAD.left + plotW) return null;
          return <line x1={sx} y1={PAD.top} x2={sx} y2={PAD.top + plotH} stroke="var(--text-muted)" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />;
        })()}
      </g>

      {/* Legend */}
      {legendItems.length > 1 && (
        <g>
          <rect x={legendX} y={legendY} width={legendW} height={legendH} rx={3}
            fill="var(--bg2)" stroke="var(--border)" strokeWidth={1} opacity={0.92} />
          {legendItems.map((s, si) => {
            const color = s.color ?? CHART_COLORS[si % CHART_COLORS.length];
            const ly = legendY + 8 + si * legendLineH;
            return (
              <g key={si}>
                <line x1={legendX + 5} y1={ly + 4} x2={legendX + 18} y2={ly + 4}
                  stroke={color} strokeWidth={s.width ?? 1.8} strokeDasharray={s.dash ? "5 2" : undefined} />
                <text x={legendX + 22} y={ly + 8} fontSize={9} fill="var(--text)" fontFamily="monospace">
                  {s.label}
                </text>
              </g>
            );
          })}
        </g>
      )}
    </svg>
    )}
    </div>
  );
}
