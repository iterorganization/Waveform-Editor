import { useCallback, useEffect, useRef, useState } from "react";
import type { TendencyInfo } from "../../types";

interface WaveformData {
  times: number[];
  values: number[];
}

interface Props {
  tendencies: TendencyInfo[];
  data: WaveformData;
  activeTendency: number | null;
  onTendencyClick: (idx: number) => void;
  onParamChange: (lineNumber: number, changes: Array<[string, number]>) => void;
  onPiecewiseChange?: (lineNumber: number, times: number[], values: number[]) => void;
  units?: string;
  /** Playback scrub time — shown as a vertical cursor line */
  currentTime?: number | null;
}

const COLORS = [
  "#4f8ef7", "#7c5cfc", "#2dd4bf", "#f97316",
  "#3ddc84", "#f59e0b", "#f472b6", "#e879f9",
];

const PAD = { top: 24, right: 24, bottom: 44, left: 72 };
const HANDLE_R = 6;

const PERIODIC_WAVE_TYPES = ["sine", "sine-wave", "triangle", "triangle-wave", "sawtooth", "sawtooth-wave", "square", "square-wave"];

type HandleKind = "from" | "to" | "value" | "amplitude_peak" | "period" | "phase" | "duration" | "start" | "end" | "piecewise_point";

interface Handle {
  tendencyIdx: number;
  kind: HandleKind;
  cx: number;
  cy: number;
  dataX: number;
  dataY: number;
  pointIndex?: number;  // for piecewise_point handles
}

interface DragState {
  tendencyIdx: number;
  kind: HandleKind;
  startClientX: number;
  startClientY: number;
  startDataX: number;
  startDataY: number;
  pointIndex?: number;  // for piecewise_point
}

interface LiveValue {
  tendencyIdx: number;
  kind: HandleKind;
  value: number;
  pointIndex?: number;  // for piecewise_point
  valueX?: number;      // time coordinate for piecewise_point
}

// Resolve the base offset for a sine tendency. If not explicit in params, derive it
// Returns the base (centre) for a periodic tendency, or the last data point before it starts.
function resolveBase(td: TendencyInfo, data: WaveformData): number {
  const p = td.params;
  if (p.min !== undefined && p.max !== undefined) return (p.min + p.max) / 2;
  if (p.base !== undefined) return p.base;
  for (let i = data.times.length - 1; i >= 0; i--) {
    if (data.times[i] < td.start_time - 1e-9) return data.values[i];
  }
  return 0;
}

// For linear/smooth tendencies that omit `from`, evaluate the immediately preceding
// tendency at its exact end time — same inference the backend does.
function resolveImpliedFrom(td: TendencyInfo, tendencies: TendencyInfo[], data: WaveformData): number {
  const tdIdx = tendencies.indexOf(td);
  if (tdIdx > 0) {
    const prev = tendencies[tdIdx - 1];
    if (Math.abs(prev.end_time - td.start_time) < 1e-6) {
      const prevBase = resolveBase(prev, data);
      return evalTendencyAt(prev, null, prev.end_time, prevBase);
    }
  }
  for (let i = data.times.length - 1; i >= 0; i--) {
    if (data.times[i] < td.start_time - 1e-9) return data.values[i];
  }
  return 0;
}

// Derivative at the END of a tendency (in data units per second).
// Used to compute boundary conditions for the cubic Hermite smooth curve.
function getEndDerivative(td: TendencyInfo, tendencies: TendencyInfo[], data: WaveformData): number {
  if (td.type === "constant" || td.type === "smooth" || td.type === "piecewise" || td.type === "repeat") return 0;
  if (td.type === "linear") {
    const from = td.params.from !== undefined ? td.params.from : resolveImpliedFrom(td, tendencies, data);
    const to = td.params.to !== undefined ? td.params.to : from;
    const dur = td.end_time - td.start_time;
    return dur > 0 ? (to - from) / dur : 0;
  }
  if (td.type === "sine-wave" || td.type === "sine") {
    const p = td.params;
    const amplitude = p.amplitude ?? (p.min !== undefined && p.max !== undefined ? (p.max - p.min) / 2 : 0);
    const period = p.period ?? (p.frequency ? 1 / p.frequency : (td.end_time - td.start_time));
    const phase = p.phase ?? 0;
    const tRel = td.end_time - td.start_time;
    return amplitude * (2 * Math.PI / period) * Math.cos(2 * Math.PI / period * tRel + phase);
  }
  return 0;
}

// Derivative at the START of a tendency.
function getStartDerivative(td: TendencyInfo, tendencies: TendencyInfo[], data: WaveformData): number {
  if (td.type === "constant" || td.type === "smooth" || td.type === "piecewise" || td.type === "repeat") return 0;
  if (td.type === "linear") {
    const from = td.params.from !== undefined ? td.params.from : resolveImpliedFrom(td, tendencies, data);
    const to = td.params.to !== undefined ? td.params.to : from;
    const dur = td.end_time - td.start_time;
    return dur > 0 ? (to - from) / dur : 0;
  }
  if (td.type === "sine-wave" || td.type === "sine") {
    const p = td.params;
    const amplitude = p.amplitude ?? (p.min !== undefined && p.max !== undefined ? (p.max - p.min) / 2 : 0);
    const period = p.period ?? (p.frequency ? 1 / p.frequency : (td.end_time - td.start_time));
    const phase = p.phase ?? 0;
    return amplitude * (2 * Math.PI / period) * Math.cos(phase);
  }
  return 0;
}

// Evaluate a tendency locally at time t, with optional live param override.
// baseOverride: pre-resolved base for sine tendencies (accounts for implicit offset).
// smoothD: boundary derivatives for smooth cubic Hermite (dStart, dEnd in value/s).
function evalTendencyAt(td: TendencyInfo, live: LiveValue | null, t: number, baseOverride?: number, smoothD?: { dStart: number; dEnd: number }): number {
  const p = { ...td.params };

  if (td.type === "constant") {
    return (live?.kind === "value") ? live.value : (p.value !== undefined ? p.value : (baseOverride ?? 0));
  }

  if (td.type === "piecewise") {
    const times = td.piecewise_times ?? [];
    const values = td.piecewise_values ?? [];
    if (!times.length) return 0;
    if (t <= times[0]) return values[0];
    if (t >= times[times.length - 1]) return values[values.length - 1];
    for (let i = 1; i < times.length; i++) {
      if (t <= times[i]) {
        const frac = (t - times[i - 1]) / (times[i] - times[i - 1]);
        return values[i - 1] + frac * (values[i] - values[i - 1]);
      }
    }
    return values[values.length - 1];
  }

  if (td.type === "linear") {
    const from = (live?.kind === "from") ? live.value : (p.from !== undefined ? p.from : (baseOverride ?? 0));
    const to   = (live?.kind === "to")   ? live.value : (p.to !== undefined ? p.to : (baseOverride ?? 0));
    const dur  = td.end_time - td.start_time;
    if (dur <= 0) return from;
    const frac = Math.max(0, Math.min(1, (t - td.start_time) / dur));
    return from + (to - from) * frac;
  }

  if (td.type === "smooth") {
    const from = (live?.kind === "from") ? live.value : (p.from !== undefined ? p.from : (baseOverride ?? 0));
    const to   = (live?.kind === "to")   ? live.value : (p.to !== undefined ? p.to : (baseOverride ?? 0));
    const dur  = td.end_time - td.start_time;
    if (dur <= 0) return from;
    const frac = Math.max(0, Math.min(1, (t - td.start_time) / dur));
    // Cubic Hermite — matches scipy CubicSpline with first-derivative BCs.
    // m0/m1 are tangents in normalised frac-space (= d/dt * dur).
    const m0 = (smoothD?.dStart ?? 0) * dur;
    const m1 = (smoothD?.dEnd   ?? 0) * dur;
    const f2 = frac * frac, f3 = f2 * frac;
    return (2*f3 - 3*f2 + 1)*from + (f3 - 2*f2 + frac)*m0 + (-2*f3 + 3*f2)*to + (f3 - f2)*m1;
  }

  if (PERIODIC_WAVE_TYPES.includes(td.type)) {
    let base: number, amplitude: number;
    if (p.min !== undefined && p.max !== undefined) {
      base = (p.min + p.max) / 2;
      amplitude = (p.max - p.min) / 2;
    } else {
      base = baseOverride !== undefined ? baseOverride : (p.base ?? 0);
      amplitude = p.amplitude ?? 0;
    }

    if (live?.kind === "amplitude_peak") {
      amplitude = Math.abs(live.value - base);
    }

    let period = p.period ?? (p.frequency ? 1 / p.frequency : (td.end_time - td.start_time));
    if (live?.kind === "period") period = Math.max(0.001, live.value);

    let phase = p.phase ?? 0;
    if (live?.kind === "phase") phase = live.value;  // horizontal drag stores phase angle directly

    if (td.type === "sine" || td.type === "sine-wave") {
      return base + amplitude * Math.sin(2 * Math.PI / period * (t - td.start_time) + phase);
    }
    if (td.type === "triangle" || td.type === "triangle-wave") {
      const theta = 2 * Math.PI / period * (t - td.start_time) + phase - Math.PI / 2;
      const thetaNorm = ((theta / Math.PI) % 2 + 2) % 2;
      return base + amplitude * (2 * Math.abs(thetaNorm - 1) - 1);
    }
    if (td.type === "sawtooth" || td.type === "sawtooth-wave") {
      const tCycleRaw = t - td.start_time + period / 2 + phase * period / (2 * Math.PI);
      const tCycle = ((tCycleRaw % period) + period) % period;
      return base + amplitude * ((tCycle / period) * 2 - 1);
    }
    if (td.type === "square" || td.type === "square-wave") {
      const tCycleRaw = t - td.start_time + phase * period / (2 * Math.PI);
      const tCycle = ((tCycleRaw % period) + period) % period;
      return base + amplitude * (tCycle < period / 2 ? 1 : -1);
    }
  }

  return 0;
}

// Generate N sample times across a tendency range.
function sampleTimes(tStart: number, tEnd: number, n: number): number[] {
  return Array.from({ length: n }, (_, i) => tStart + (i / (n - 1)) * (tEnd - tStart));
}

function niceTickValues(min: number, max: number, count: number): number[] {
  if (!isFinite(min) || !isFinite(max) || min >= max) return isFinite(min) ? [min] : [];
  const range = max - min;
  // Below float resolution: a step this small cannot advance the loop (v += step === v)
  if (range < (Math.abs(min) + Math.abs(max)) * 1e-12) return [min];
  const raw = range / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = norm < 1.5 ? mag : norm < 3.5 ? 2 * mag : norm < 7.5 ? 5 * mag : 10 * mag;
  if (!(step > 0)) return [min, max]; // guard against NaN/0 step
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 0.01 && ticks.length < 500; v += step) {
    ticks.push(parseFloat(v.toPrecision(10)));
  }
  return ticks;
}

function fmtVal(v: number): string {
  const abs = Math.abs(v);
  if (abs === 0) return "0";
  if (abs >= 1e6 || (abs < 1e-3 && abs > 0)) return v.toExponential(2);
  if (abs >= 100) return v.toFixed(1);
  if (abs >= 10) return v.toFixed(2);
  return v.toFixed(3);
}

export function WaveformPlot({ tendencies, data, activeTendency, onTendencyClick, onParamChange, onPiecewiseChange, units, currentTime }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({ w: 800, h: 400 });
  const [hovered, setHovered] = useState<number | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [liveValue, setLiveValue] = useState<LiveValue | null>(null);
  const [viewRange, setViewRange] = useState<{ tMin: number; tMax: number; vMin: number; vMax: number } | null>(null);
  const [panState, setPanState] = useState<{ startClientX: number; startClientY: number; startView: { tMin: number; tMax: number; vMin: number; vMax: number } } | null>(null);

  // Piecewise editing mode: true = add-point mode, false = pan/navigate mode
  const [piecewiseEditMode, setPiecewiseEditMode] = useState(true);
  // Records mousedown position so we can ignore accidental clicks from small drags
  const piecewisePressRef = useRef<{ x: number; y: number } | null>(null);

  // Reset to edit mode whenever the active tendency changes
  useEffect(() => { setPiecewiseEditMode(true); }, [activeTendency]);

  // Ref so onUp can read the latest liveValue without being in effect deps
  const liveValueRef = useRef<LiveValue | null>(null);
  useEffect(() => { liveValueRef.current = liveValue; }, [liveValue]);
  // Wheel handler stored in ref so a single stable listener always calls the latest version
  const wheelHandlerRef = useRef<((e: WheelEvent) => void) | null>(null);

  useEffect(() => {
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setSize({ w: width, h: height });
    });
    if (svgRef.current) obs.observe(svgRef.current.parentElement!);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const handler = (e: WheelEvent) => wheelHandlerRef.current?.(e);
    svg.addEventListener("wheel", handler, { passive: false });
    return () => svg.removeEventListener("wheel", handler);
  }, []);

  const plotW = size.w - PAD.left - PAD.right;
  const plotH = size.h - PAD.top - PAD.bottom;

  // Use the waveform's own tendency time range as the natural view extent so the
  // plot isn't dwarfed by the global time range when other waveforms are much longer.
  const wfTStart = tendencies.length > 0 ? tendencies[0].start_time : (data.times.length ? data.times[0] : 0);
  const wfTEnd   = tendencies.length > 0 ? tendencies[tendencies.length - 1].end_time : (data.times.length ? data.times[data.times.length - 1] : 100);
  const dataTMin = wfTStart;
  const dataTMax = wfTEnd;

  // Y range from values within the waveform's own time range only (values outside
  // may be 0 or NaN and would incorrectly compress the scale).
  const wfValues = data.values.filter((_, i) => data.times[i] >= wfTStart - 1e-9 && data.times[i] <= wfTEnd + 1e-9);
  let rawVMin = wfValues.length ? Math.min(...wfValues) : -1;
  let rawVMax = wfValues.length ? Math.max(...wfValues) : 1;
  // Relative epsilon: spans below float resolution degenerate the same as exact equality
  if (rawVMax - rawVMin < (Math.abs(rawVMin) + Math.abs(rawVMax)) * 1e-12) {
    const bump = Math.max(Math.abs(rawVMax) * 0.05, 1);
    rawVMin -= bump; rawVMax += bump;
  }
  const vPad = (rawVMax - rawVMin) * 0.15;
  const dataVMin = rawVMin - vPad;
  const dataVMax = rawVMax + vPad;

  // Effective view range — viewRange overrides the natural data extent when set
  const tMin = viewRange?.tMin ?? dataTMin;
  const tMax = viewRange?.tMax ?? dataTMax;
  const vMin = viewRange?.vMin ?? dataVMin;
  const vMax = viewRange?.vMax ?? dataVMax;

  const toSvgX = useCallback((t: number) =>
    PAD.left + ((t - tMin) / (tMax - tMin || 1)) * plotW,
    [tMin, tMax, plotW]);

  const toSvgY = useCallback((v: number) =>
    PAD.top + (1 - (v - vMin) / (vMax - vMin || 1)) * plotH,
    [vMin, vMax, plotH]);

  const fromSvgY = useCallback((y: number) =>
    vMin + (1 - (y - PAD.top) / (plotH || 1)) * (vMax - vMin),
    [vMin, vMax, plotH]);

  const fromSvgX = useCallback((x: number) =>
    tMin + ((x - PAD.left) / (plotW || 1)) * (tMax - tMin),
    [tMin, tMax, plotW]);

  // Assigned every render so the stable wheel listener always sees current ranges
  wheelHandlerRef.current = (e: WheelEvent) => {
    e.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const svgMouseX = (e.clientX - rect.left) * (size.w / rect.width);
    const mouseT = tMin + ((svgMouseX - PAD.left) / (plotW || 1)) * (tMax - tMin);
    const factor = e.deltaY > 0 ? 1.15 : 1 / 1.15;
    const newTMin = mouseT - (mouseT - tMin) * factor;
    const newTMax = mouseT + (tMax - mouseT) * factor;
    if (newTMax - newTMin < 1e-9) return; // prevent zoom-in so far tMin ≈ tMax
    setViewRange({ tMin: newTMin, tMax: newTMax, vMin, vMax });
  };

  // Build per-tendency paths — use local evaluation when dragging that tendency
  const tendencyPaths = tendencies.map((td, i) => {
    const isLive = liveValue?.tendencyIdx === i;
    if (isLive) {
      // Compute locally for instant visual feedback — no API round-trip needed
      const lv = liveValue!;

      if (lv.kind === "piecewise_point") {
        const pi = lv.pointIndex!;
        const times = [...(td.piecewise_times ?? [])];
        const values = [...(td.piecewise_values ?? [])];
        times[pi] = lv.valueX !== undefined ? lv.valueX : times[pi];
        values[pi] = lv.value;
        return times.map((t, j) => `${j === 0 ? "M" : "L"} ${toSvgX(t)} ${toSvgY(values[j])}`).join(" ");
      }

      const isTimeDrag = lv.kind === "duration" || lv.kind === "start" || lv.kind === "end";
      const tdLive = lv.kind === "duration"
        ? { ...td, end_time: td.start_time + Math.max(0.001, lv.value) }
        : lv.kind === "start" ? { ...td, start_time: lv.value }
        : lv.kind === "end"   ? { ...td, end_time: lv.value }
        : td;
      const liveRef = isTimeDrag ? null : lv;
      const liveStart = tdLive.start_time;
      const liveEnd = tdLive.end_time;
      if (liveEnd <= liveStart) return "";
      const isPeriodicType = PERIODIC_WAVE_TYPES.includes(td.type);
      const isLinearMissingFrom = (td.type === "linear" || td.type === "smooth") && !("from" in td.params);
      const isConstantNoValue = td.type === "constant" && !("value" in td.params);
      const baseOverride = isPeriodicType
        ? resolveBase(td, data)
        : (isLinearMissingFrom || isConstantNoValue) ? resolveImpliedFrom(td, tendencies, data) : undefined;
      // Boundary derivatives for smooth cubic Hermite — derive from adjacent tendencies.
      let smoothD: { dStart: number; dEnd: number } | undefined;
      if (td.type === "smooth") {
        let dStart = 0, dEnd = 0;
        if (i > 0 && Math.abs(tendencies[i - 1].end_time - td.start_time) < 1e-6)
          dStart = getEndDerivative(tendencies[i - 1], tendencies, data);
        if (i < tendencies.length - 1 && Math.abs(tendencies[i + 1].start_time - td.end_time) < 1e-6)
          dEnd = getStartDerivative(tendencies[i + 1], tendencies, data);
        smoothD = { dStart, dEnd };
      }
      const tdP = td.params;
      const livePeriod = isPeriodicType
        ? (tdP.period ?? (tdP.frequency ? 1 / tdP.frequency : (liveEnd - liveStart)))
        : (liveEnd - liveStart);
      const dur = liveEnd - liveStart;
      const nLive = isPeriodicType
        ? Math.min(4000, Math.max(120, Math.ceil(dur / livePeriod * 60)))
        : 400;
      const livePts = sampleTimes(liveStart, liveEnd, nLive).map((t) => ({
        t,
        v: evalTendencyAt(tdLive, liveRef, t, baseOverride, smoothD),
      }));
      return livePts.map((q, j) => `${j === 0 ? "M" : "L"} ${toSvgX(q.t)} ${toSvgY(q.v)}`).join(" ");
    }
    // Piecewise: render directly from the control points (straight lines between them)
    if (td.type === "piecewise") {
      const pts = td.piecewise_times ?? [];
      const vals = td.piecewise_values ?? [];
      if (!pts.length) return "";
      return pts.map((t, j) => `${j === 0 ? "M" : "L"} ${toSvgX(t)} ${toSvgY(vals[j])}`).join(" ");
    }

    // Smooth periodic tendencies: resample locally at high density (60 pts/period).
    // Sawtooth and square have discontinuities — use data array (API returns exact transition points).
    if (td.type === "sine" || td.type === "sine-wave" || td.type === "triangle" || td.type === "triangle-wave") {
      const tdPeriod = td.params.period ?? (td.params.frequency ? 1 / td.params.frequency : (td.end_time - td.start_time));
      const dur = td.end_time - td.start_time;
      const nPts = Math.min(4000, Math.max(120, Math.ceil(dur / tdPeriod * 60)));
      const tdBase = resolveBase(td, data);
      return sampleTimes(td.start_time, td.end_time, nPts)
        .map((t, j) => `${j === 0 ? "M" : "L"} ${toSvgX(t)} ${toSvgY(evalTendencyAt(td, null, t, tdBase))}`)
        .join(" ");
    }

    const pts = data.times.flatMap((t, j) => {
      const inRange = t >= td.start_time - 1e-9 && t <= td.end_time + 1e-9;
      return inRange ? [{ t, v: data.values[j] }] : [];
    });
    // Inject exact boundary points so tendency edges connect cleanly.
    const isLinearNoFrom = (td.type === "linear" || td.type === "smooth") && !("from" in td.params);
    const isConstantNoVal = td.type === "constant" && !("value" in td.params);
    const boundaryBase = PERIODIC_WAVE_TYPES.includes(td.type)
      ? resolveBase(td, data)
      : (isLinearNoFrom || isConstantNoVal) ? resolveImpliedFrom(td, tendencies, data) : undefined;
    if (!pts.length || pts[0].t > td.start_time + 1e-9) {
      pts.unshift({ t: td.start_time, v: evalTendencyAt(td, null, td.start_time, boundaryBase) });
    }
    if (!pts.length || pts[pts.length - 1].t < td.end_time - 1e-9) {
      pts.push({ t: td.end_time, v: evalTendencyAt(td, null, td.end_time, boundaryBase) });
    }
    return pts.map((p, j) => `${j === 0 ? "M" : "L"} ${toSvgX(p.t)} ${toSvgY(p.v)}`).join(" ");
  });

  // Compute drag handles per tendency
  const getHandles = (td: TendencyInfo, idx: number): Handle[] => {
    const p = td.params;
    const handles: Handle[] = [];
    const tStart = td.start_time;
    const tEnd = td.end_time;
    const tMid = (tStart + tEnd) / 2;

    const applyLive = (kind: HandleKind, defaultY: number) => {
      if (liveValue && liveValue.tendencyIdx === idx && liveValue.kind === kind)
        return liveValue.value;
      return defaultY;
    };

    if (td.type === "constant") {
      // Show handle even when value is implicit (inferred from previous tendency).
      // Dragging writes an explicit value: into the YAML.
      const impliedV = p.value !== undefined ? p.value : resolveImpliedFrom(td, tendencies, data);
      const v = applyLive("value", impliedV);
      handles.push({ tendencyIdx: idx, kind: "value", cx: toSvgX(tMid), cy: toSvgY(v), dataX: tMid, dataY: v });
    } else if (td.type === "linear" || td.type === "smooth") {
      if (p.from !== undefined) {
        const fromV = applyLive("from", p.from);
        handles.push({ tendencyIdx: idx, kind: "from", cx: toSvgX(tStart), cy: toSvgY(fromV), dataX: tStart, dataY: fromV });
      }
      if (p.to !== undefined) {
        const toV = applyLive("to", p.to);
        handles.push({ tendencyIdx: idx, kind: "to", cx: toSvgX(tEnd), cy: toSvgY(toV), dataX: tEnd, dataY: toV });
      }
    } else if (PERIODIC_WAVE_TYPES.includes(td.type)) {
      let base: number, amplitude: number;
      if (p.min !== undefined && p.max !== undefined) {
        base = (p.min + p.max) / 2;
        amplitude = (p.max - p.min) / 2;
      } else {
        base = resolveBase(td, data);
        amplitude = p.amplitude ?? 0;
      }
      const period = p.period ?? (p.frequency ? 1 / p.frequency : (tEnd - tStart));
      const phase = p.phase ?? 0;
      const liveForThis = liveValue?.tendencyIdx === idx ? liveValue : null;
      const evalAt = (t: number) => evalTendencyAt(td, liveForThis, t, base);

      if (p.min !== undefined || p.max !== undefined || p.amplitude !== undefined) {
        let clampedPeakT: number;
        if (td.type === "sine" || td.type === "sine-wave" || td.type === "triangle" || td.type === "triangle-wave") {
          // Exact formula: first peak at tStart + T/4 - phase*T/(2π) (same for sine and triangle)
          const peakT0 = tStart + period / 4 - phase * period / (2 * Math.PI);
          const k = Math.ceil((tStart - peakT0) / period);
          const peakTInRange = peakT0 + Math.max(0, k) * period;
          clampedPeakT = Math.max(tStart, Math.min(tEnd, peakTInRange));
        } else {
          // Sawtooth/square: sample to find first maximum in range
          const n = Math.min(1000, Math.max(60, Math.ceil((tEnd - tStart) / period * 40)));
          const ts = sampleTimes(tStart, tEnd, n);
          let bestT = tStart, bestV = -Infinity;
          for (const t of ts) {
            const v = evalTendencyAt(td, null, t, base);
            if (v > bestV) { bestV = v; bestT = t; }
          }
          clampedPeakT = bestT;
        }
        const peakV = applyLive("amplitude_peak", base + amplitude);
        handles.push({ tendencyIdx: idx, kind: "amplitude_peak", cx: toSvgX(clampedPeakT), cy: toSvgY(peakV), dataX: clampedPeakT, dataY: peakV });
      }

      if (p.period !== undefined || p.frequency !== undefined) {
        const effectivePeriod = liveForThis?.kind === "period" ? liveForThis.value : period;
        const periodHandleT = Math.min(tEnd, tStart + effectivePeriod);
        const periodHandleY = evalAt(periodHandleT);
        handles.push({ tendencyIdx: idx, kind: "period", cx: toSvgX(periodHandleT), cy: toSvgY(periodHandleY), dataX: periodHandleT, dataY: periodHandleY });
      }

      if (p.phase !== undefined) {
        // Phase handle: horizontal position encodes phase as offset within one period.
        // Dragging right increases phase (wave shifts left in time).
        const effectivePhase = liveForThis?.kind === "phase" ? liveForThis.value : phase;
        const phaseOffset = ((-effectivePhase % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
        const phaseHandleT = Math.max(tStart, Math.min(tEnd, tStart + phaseOffset * period / (2 * Math.PI)));
        handles.push({ tendencyIdx: idx, kind: "phase", cx: toSvgX(phaseHandleT), cy: toSvgY(base), dataX: phaseHandleT, dataY: base });
      }
    }
    // Time boundary handles — vertical arrow bars, staggered vertically so overlapping
    // handles (e.g. both `end` and `duration`) remain independently clickable.
    const liveForThis = liveValue?.tendencyIdx === idx ? liveValue : null;
    const tLineTop = PAD.top + 6;
    const tLineLen = plotH - 12;
    if ('start' in td.params) {
      const effectiveT = liveForThis?.kind === "start" ? liveForThis.value : td.start_time;
      handles.push({
        tendencyIdx: idx, kind: "start",
        cx: toSvgX(effectiveT), cy: tLineTop + tLineLen * 0.25,
        dataX: effectiveT, dataY: (vMin + vMax) / 2,
      });
    }
    if ('end' in td.params) {
      const effectiveT = liveForThis?.kind === "end" ? liveForThis.value : td.end_time;
      handles.push({
        tendencyIdx: idx, kind: "end",
        cx: toSvgX(effectiveT), cy: tLineTop + tLineLen * 0.75,
        dataX: effectiveT, dataY: (vMin + vMax) / 2,
      });
    }
    if ('duration' in td.params) {
      const effectiveDur = liveForThis?.kind === "duration" ? liveForThis.value : (td.params.duration ?? (td.end_time - td.start_time));
      const durEndT = td.start_time + Math.max(0.001, effectiveDur);
      handles.push({
        tendencyIdx: idx, kind: "duration",
        cx: toSvgX(durEndT), cy: tLineTop + tLineLen * 0.50,
        dataX: durEndT, dataY: (vMin + vMax) / 2,
      });
    }

    if (td.type === "piecewise") {
      const pts = td.piecewise_times ?? [];
      const vals = td.piecewise_values ?? [];
      for (let pi = 0; pi < pts.length; pi++) {
        let hT = pts[pi], hV = vals[pi];
        if (liveForThis?.kind === "piecewise_point" && liveForThis.pointIndex === pi) {
          hT = liveForThis.valueX ?? hT;
          hV = liveForThis.value;
        }
        handles.push({
          tendencyIdx: idx, kind: "piecewise_point", pointIndex: pi,
          cx: toSvgX(hT), cy: toSvgY(hV), dataX: hT, dataY: hV,
        });
      }
    }

    return handles;
  };

  const allHandles = tendencies.flatMap((td, i) => getHandles(td, i));

  // Helper: apply handle change to YAML — builds the changes array for one atomic update
  const applyHandleChange = useCallback((lv: LiveValue) => {
    const { tendencyIdx, kind, value } = lv;
    const td = tendencies[tendencyIdx];
    if (!td) return;
    const p = td.params;

    if (kind === "piecewise_point") {
      const pi = lv.pointIndex!;
      const times = [...(td.piecewise_times ?? [])];
      const values = [...(td.piecewise_values ?? [])];
      times[pi] = lv.valueX !== undefined ? lv.valueX : times[pi];
      values[pi] = value;
      onPiecewiseChange?.(td.line_number, times, values);
      return;
    }
    const base = (p.min !== undefined && p.max !== undefined)
      ? (p.min + p.max) / 2 : resolveBase(td, data);
    if (kind === "amplitude_peak") {
      const amp = Math.abs(value - base);
      if (p.min !== undefined || p.max !== undefined) {
        onParamChange(td.line_number, [["min", base - amp], ["max", base + amp]]);
      } else {
        onParamChange(td.line_number, [["amplitude", amp]]);
      }
    } else if (kind === "phase") {
      onParamChange(td.line_number, [["phase", value]]);
    } else if (kind === "period") {
      // YAML might use `frequency` instead of `period` — convert if needed
      if (td.params.frequency !== undefined && td.params.period === undefined) {
        onParamChange(td.line_number, [["frequency", 1 / Math.max(1e-9, value)]]);
      } else {
        onParamChange(td.line_number, [["period", value]]);
      }
    } else if (kind === "duration") {
      onParamChange(td.line_number, [["duration", Math.max(0.001, value)]]);
    } else if (kind === "start") {
      onParamChange(td.line_number, [["start", value]]);
    } else if (kind === "end") {
      onParamChange(td.line_number, [["end", value]]);
    } else {
      onParamChange(td.line_number, [[kind, value]]);
    }
  }, [tendencies, data, onParamChange, onPiecewiseChange]);

  // Mouse drag wiring
  useEffect(() => {
    if (!dragState) return;

    const onMove = (e: MouseEvent) => {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const scaleX = size.w / rect.width;
      const scaleY = size.h / rect.height;
      const svgX = (e.clientX - rect.left) * scaleX;
      const svgY = (e.clientY - rect.top) * scaleY;

      const { kind, tendencyIdx } = dragState;
      const td = tendencies[tendencyIdx];

      if (kind === "piecewise_point") {
        const pi = dragState.pointIndex!;
        const pts = td.piecewise_times ?? [];
        const newT = fromSvgX(svgX);
        const newV = fromSvgY(svgY);
        // Clamp time between neighbouring points to preserve monotonicity
        const minT = pi > 0 ? pts[pi - 1] + 1e-6 : -Infinity;
        const maxT = pi < pts.length - 1 ? pts[pi + 1] - 1e-6 : Infinity;
        setLiveValue({
          tendencyIdx, kind: "piecewise_point",
          value: newV,
          valueX: Math.max(minT, Math.min(maxT, newT)),
          pointIndex: pi,
        });
        return;
      }

      let newValue: number;
      if (kind === "period" || kind === "duration") {
        newValue = Math.max(0.001, fromSvgX(svgX) - td.start_time);
      } else if (kind === "start" || kind === "end") {
        newValue = fromSvgX(svgX);
      } else if (kind === "phase") {
        const tdP = td.params;
        const period = tdP.period ?? (tdP.frequency ? 1 / tdP.frequency : (td.end_time - td.start_time));
        newValue = -(fromSvgX(svgX) - td.start_time) * 2 * Math.PI / period;
      } else {
        newValue = fromSvgY(svgY);
      }

      setLiveValue({ tendencyIdx, kind, value: newValue });
    };

    const onUp = () => {
      // Commit the final value (in case the last throttled call was skipped)
      const lv = liveValueRef.current;
      if (lv) {
        applyHandleChange(lv);
      }
      setDragState(null);
      setLiveValue(null);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragState, tendencies, fromSvgX, fromSvgY, applyHandleChange, size]);

  const startDrag = (e: React.MouseEvent, h: Handle) => {
    e.preventDefault();
    e.stopPropagation();
    setDragState({
      tendencyIdx: h.tendencyIdx,
      kind: h.kind,
      startClientX: e.clientX,
      startClientY: e.clientY,
      startDataX: h.dataX,
      startDataY: h.dataY,
      pointIndex: h.pointIndex,
    });
  };

  // Path click just selects — add-point is handled by the piecewise area rect in edit mode
  const handlePathClick = useCallback((_e: React.MouseEvent, _td: TendencyInfo | undefined, i: number) => {
    onTendencyClick(i);
  }, [onTendencyClick]);

  const startPan = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0 || dragState) return;
    e.preventDefault();
    setPanState({ startClientX: e.clientX, startClientY: e.clientY, startView: { tMin, tMax, vMin, vMax } });
  }, [dragState, tMin, tMax, vMin, vMax]);

  useEffect(() => {
    if (!panState) return;
    const onMove = (e: MouseEvent) => {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const dx = (e.clientX - panState.startClientX) * (size.w / rect.width);
      const dy = (e.clientY - panState.startClientY) * (size.h / rect.height);
      const { startView: sv } = panState;
      const dtPx = (sv.tMax - sv.tMin) / plotW;
      const dvPx = (sv.vMax - sv.vMin) / plotH;
      setViewRange({ tMin: sv.tMin - dx * dtPx, tMax: sv.tMax - dx * dtPx, vMin: sv.vMin + dy * dvPx, vMax: sv.vMax + dy * dvPx });
    };
    const onUp = () => setPanState(null);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [panState, plotW, plotH, size]);

  const handleDoubleClick = useCallback(() => setViewRange(null), []);

  // Grid ticks
  const xTicks = niceTickValues(tMin, tMax, Math.max(3, Math.floor(plotW / 90)));
  const yTicks = niceTickValues(vMin, vMax, Math.max(3, Math.floor(plotH / 55)));

  const activePiecewise = activeTendency !== null && tendencies[activeTendency]?.type === "piecewise";

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
    {/* Mode toggle — shown only when a piecewise tendency is active */}
    {activePiecewise && (
      <div className="pw-mode-toggle">
        <button
          className={`pw-mode-btn${piecewiseEditMode ? " active" : ""}`}
          onClick={() => setPiecewiseEditMode(true)}
          title="Edit mode: click to add points, drag handles to move"
        >✎ Points</button>
        <button
          className={`pw-mode-btn${!piecewiseEditMode ? " active" : ""}`}
          onClick={() => setPiecewiseEditMode(false)}
          title="Navigate mode: pan and zoom"
        >✋ Pan</button>
      </div>
    )}
    <svg
      ref={svgRef}
      width={size.w}
      height={size.h}
      onDoubleClick={handleDoubleClick}
      style={{ display: "block", userSelect: "none", cursor: dragState ? (dragState.kind === "piecewise_point" ? "move" : (dragState.kind === "period" || dragState.kind === "phase" || dragState.kind === "duration" || dragState.kind === "start" || dragState.kind === "end") ? "ew-resize" : "ns-resize") : panState ? "grabbing" : "default" }}
    >
      {/* Plot background — mousedown here starts pan; double-click resets view */}
      <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} fill="var(--bg)" rx={2}
        style={{ cursor: panState ? "grabbing" : "grab" }}
        onMouseDown={startPan}
      />

      {/* Y grid lines + labels */}
      {yTicks.map((v) => {
        const y = toSvgY(v);
        if (y < PAD.top || y > PAD.top + plotH) return null;
        return (
          <g key={`yg-${v}`}>
            <line x1={PAD.left} y1={y} x2={PAD.left + plotW} y2={y}
              stroke="var(--border)" strokeWidth={1} strokeDasharray="3 4" opacity={0.55} />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize={10}
              fill="var(--text-muted)" fontFamily="monospace">
              {fmtVal(v)}
            </text>
          </g>
        );
      })}

      {/* X grid lines + labels */}
      {xTicks.map((t) => {
        const x = toSvgX(t);
        if (x < PAD.left || x > PAD.left + plotW) return null;
        return (
          <g key={`xg-${t}`}>
            <line x1={x} y1={PAD.top} x2={x} y2={PAD.top + plotH}
              stroke="var(--border)" strokeWidth={1} strokeDasharray="3 4" opacity={0.55} />
            <text x={x} y={PAD.top + plotH + 16} textAnchor="middle"
              fontSize={10} fill="var(--text-muted)" fontFamily="monospace">
              {t}
            </text>
          </g>
        );
      })}

      {/* Playback time cursor */}
      {currentTime != null && (() => {
        const cx = toSvgX(currentTime);
        if (cx < PAD.left || cx > PAD.left + plotW) return null;
        return (
          <line x1={cx} y1={PAD.top} x2={cx} y2={PAD.top + plotH}
            stroke="var(--accent, #4f8ef7)" strokeWidth={1.2} strokeDasharray="4 3" opacity={0.7} />
        );
      })()}

      {/* Axis borders */}
      <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH}
        fill="none" stroke="var(--border)" strokeWidth={1} />

      {/* X label */}
      <text x={PAD.left + plotW / 2} y={size.h - 4} textAnchor="middle"
        fontSize={11} fill="var(--text-muted)">
        time (s)
      </text>

      {/* Y label */}
      <text
        x={12} y={PAD.top + plotH / 2}
        textAnchor="middle"
        fontSize={11} fill="var(--text-muted)"
        transform={`rotate(-90, 12, ${PAD.top + plotH / 2})`}
      >
        {units || "value"}
      </text>

      {/* Clip path for tendency paths */}
      <defs>
        <clipPath id="plot-clip">
          <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH} />
        </clipPath>
      </defs>

      {/* Tendency paths — dimmed when another is active */}
      <g clipPath="url(#plot-clip)">
        {tendencyPaths.map((d, i) => {
          const td = tendencies[i];
          const color = COLORS[i % COLORS.length];
          const isActive = activeTendency === i;
          const isHovered = hovered === i;
          const dimmed = activeTendency !== null && !isActive;
          return (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={color}
              strokeWidth={isActive ? 3 : isHovered ? 2.5 : 2}
              opacity={dimmed ? 0.25 : 1}
              style={{ cursor: "pointer", filter: isActive ? `drop-shadow(0 0 4px ${color}88)` : undefined }}
              onClick={(e) => handlePathClick(e, td, i)}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
            />
          );
        })}
      </g>

      {/* Tendency hit-areas (wider invisible paths for easier clicking) */}
      <g clipPath="url(#plot-clip)">
        {tendencyPaths.map((d, i) => (
          <path
            key={`hit-${i}`}
            d={d}
            fill="none"
            stroke="transparent"
            strokeWidth={14}
            style={{ cursor: "pointer" }}
            onClick={(e) => handlePathClick(e, tendencies[i], i)}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
          />
        ))}
      </g>

      {/* Piecewise edit-mode click zone — intercepts clicks to add new points;
          rendered above hit-areas but below handles so handles keep priority. */}
      {activeTendency !== null && tendencies[activeTendency]?.type === "piecewise" && piecewiseEditMode && (() => {
        const td = tendencies[activeTendency];
        const x1 = Math.max(PAD.left, toSvgX(td.start_time));
        const x2 = Math.min(PAD.left + plotW, toSvgX(td.end_time));
        if (x2 <= x1) return null;
        const color = COLORS[activeTendency % COLORS.length];
        return (
          <rect
            key="pw-click-zone"
            x={x1} y={PAD.top} width={x2 - x1} height={plotH}
            fill={color} fillOpacity={0.04}
            style={{ cursor: "crosshair" }}
            onMouseDown={(e) => { piecewisePressRef.current = { x: e.clientX, y: e.clientY }; }}
            onClick={(e) => {
              const press = piecewisePressRef.current;
              piecewisePressRef.current = null;
              if (press && (Math.abs(e.clientX - press.x) > 5 || Math.abs(e.clientY - press.y) > 5)) return;
              const svgEl = svgRef.current!.getBoundingClientRect();
              const svgX = (e.clientX - svgEl.left) * (size.w / svgEl.width);
              const svgY = (e.clientY - svgEl.top) * (size.h / svgEl.height);
              const t = fromSvgX(svgX);
              const v = fromSvgY(svgY);
              const times = td.piecewise_times ?? [];
              if (times.some(ti => Math.abs(ti - t) < 0.001)) return;
              const values = td.piecewise_values ?? [];
              const insertIdx = times.findIndex(ti => ti > t);
              const newTimes = [...times], newValues = [...values];
              if (insertIdx === -1) { newTimes.push(t); newValues.push(v); }
              else { newTimes.splice(insertIdx, 0, t); newValues.splice(insertIdx, 0, v); }
              onPiecewiseChange?.(td.line_number, newTimes, newValues);
            }}
          />
        );
      })()}

      {/* Drag handles — bars rendered before circles so value circles sit on top
          and intercept clicks even when sharing the same x position. */}
      {allHandles.map((h, hi) => {
        if (!(h.kind === "start" || h.kind === "end" || h.kind === "duration")) return null;
        const color = COLORS[h.tendencyIdx % COLORS.length];
        if (!(activeTendency === h.tendencyIdx || activeTendency === null)) return null;
        if (h.cx < PAD.left - 2 || h.cx > PAD.left + plotW + 2) return null;
        const isDragging = dragState?.tendencyIdx === h.tendencyIdx && dragState.kind === h.kind;
        const isHoveredT = hovered === h.tendencyIdx;
        const lineTop = PAD.top + 6;
        const lineBottom = PAD.top + plotH - 6;
        const arrowY = h.cy;
        const alpha = isDragging ? 0.95 : isHoveredT ? 0.8 : 0.55;
        const showLeft  = h.kind === "start" || h.kind === "duration";
        const showRight = h.kind === "end"   || h.kind === "duration";
        const label = h.kind === "duration" ? "dur" : h.kind;
        return (
          <g key={`tb-${hi}`} style={{ cursor: "ew-resize" }} onMouseDown={(e) => startDrag(e, h)}>
            <rect x={h.cx - 8} y={h.cy - 14} width={16} height={28} fill="transparent" />
            <line x1={h.cx} y1={lineTop} x2={h.cx} y2={lineBottom}
              stroke={color} strokeWidth={isDragging ? 2.5 : 1.5} opacity={alpha} />
            {showLeft && (
              <polygon points={`${h.cx - 9},${arrowY} ${h.cx - 3},${arrowY - 5} ${h.cx - 3},${arrowY + 5}`}
                fill={color} opacity={alpha} />
            )}
            {showRight && (
              <polygon points={`${h.cx + 9},${arrowY} ${h.cx + 3},${arrowY - 5} ${h.cx + 3},${arrowY + 5}`}
                fill={color} opacity={alpha} />
            )}
            {(isDragging || isHoveredT) && (
              <text x={h.cx + 12} y={arrowY + 4} fontSize={9} fill={color} fontFamily="monospace" opacity={0.85}>
                {label}
              </text>
            )}
          </g>
        );
      })}
      {allHandles.map((h, hi) => {
        if (h.kind === "start" || h.kind === "end" || h.kind === "duration") return null;
        const color = COLORS[h.tendencyIdx % COLORS.length];
        if (!(activeTendency === h.tendencyIdx || activeTendency === null)) return null;
        const isDragging = dragState?.tendencyIdx === h.tendencyIdx
          && dragState.kind === h.kind
          && (h.kind !== "piecewise_point" || dragState.pointIndex === h.pointIndex);
        const isHoveredT = hovered === h.tendencyIdx;
        const cursor = (h.kind === "period" || h.kind === "phase") ? "ew-resize"
          : h.kind === "piecewise_point" ? "move"
          : "ns-resize";
        return (
          <g key={`vc-${hi}`}>
            <circle cx={h.cx} cy={h.cy} r={isDragging ? HANDLE_R + 3 : HANDLE_R + 2}
              fill="none" stroke={color} strokeWidth={1.5} opacity={0.4} />
            <circle cx={h.cx} cy={h.cy} r={isDragging ? HANDLE_R + 1 : HANDLE_R}
              fill={isDragging ? color : "var(--bg2)"} stroke={color} strokeWidth={2}
              style={{ cursor }} onMouseDown={(e) => startDrag(e, h)} />
            {(isDragging || isHoveredT) && (
              <text x={h.cx + HANDLE_R + 5} y={h.cy + 4} fontSize={9} fill={color}
                fontFamily="monospace" opacity={0.85}>
                {h.kind === "amplitude_peak" ? "amp"
                  : h.kind === "piecewise_point" ? `pt${h.pointIndex}`
                  : h.kind === "period" ? "period"
                  : h.kind === "phase" ? "phase"
                  : h.kind}
              </text>
            )}
          </g>
        );
      })}

      {/* Live drag value tooltip */}
      {liveValue && (() => {
        const h = allHandles.find(h =>
          h.tendencyIdx === liveValue.tendencyIdx
          && h.kind === liveValue.kind
          && (h.kind !== "piecewise_point" || h.pointIndex === liveValue.pointIndex)
        );
        if (!h) return null;
        const color = COLORS[liveValue.tendencyIdx % COLORS.length];
        const label = liveValue.kind === "piecewise_point"
          ? `(${fmtVal(liveValue.valueX ?? h.dataX)}, ${fmtVal(liveValue.value)})`
          : fmtVal(liveValue.value);
        return (
          <g>
            <rect x={h.cx + 10} y={h.cy - 18} width={liveValue.kind === "piecewise_point" ? 130 : 80} height={18} rx={3}
              fill="var(--bg3)" stroke={color} strokeWidth={1} opacity={0.9} />
            <text x={h.cx + 14} y={h.cy - 4} fontSize={11} fill={color} fontFamily="monospace">
              {label}
            </text>
          </g>
        );
      })()}
    </svg>
    </div>
  );
}
