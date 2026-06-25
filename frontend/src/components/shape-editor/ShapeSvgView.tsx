import { useCallback, useEffect, useRef, useState } from "react";
import type { GapDefinition, MachineGeometries, TimestepResult } from "../../types";

// ── Three-arc plasma outline (ported from NICE / Blaise Faugeras) ─────────────
// Constructs the plasma boundary using the correct divertor geometry:
// arc 1 (outer/top/inner midplane, θ: 0→π), arc 2 (inner divertor leg),
// arc 3 (outer divertor leg), then the explicit x-point, sorted by angle.

function computeOutlineFromParams(
  a: number, center_r: number, center_z: number,
  kappa: number, delta: number, rx: number, zx: number,
  n = 121,
): { R: number[]; Z: number[] } {
  const pts: [number, number][] = [];
  const r0 = center_r, z0 = center_z;

  let nb1 = Math.floor((n - 1) / 2);
  const rem1 = (n - 1) % 2;
  let nb2 = Math.floor((rem1 + nb1) / 2);
  const nb3 = nb2;
  if ((rem1 + nb1) % 2 === 1) nb1 += 1;

  const asinD = Math.asin(Math.max(-0.99, Math.min(0.99, delta)));
  for (let i = 0; i < nb1; i++) {
    const th = (i * Math.PI) / (nb1 - 1);
    pts.push([r0 + a * Math.cos(th + asinD * Math.sin(th)), z0 + a * kappa * Math.sin(th)]);
  }

  const denom2 = rx - r0 + a;
  if (Math.abs(denom2) > 1e-6) {
    const ri = (rx + r0 - a) / 2 + (z0 - zx) ** 2 / (2 * denom2);
    const ai = ri - r0 + a;
    if (Math.abs(ai) > 1e-6) {
      const th2 = Math.asin(Math.max(-1, Math.min(1, (z0 - zx) / ai))) / (nb2 + 1);
      for (let i = 0; i < nb2; i++) {
        const th = (i + 1) * th2;
        pts.push([ri - ai * Math.cos(th), z0 - ai * Math.sin(th)]);
      }
    }
  }

  const denom3 = rx - r0 - a;
  if (Math.abs(denom3) > 1e-6) {
    const re = (rx + r0 + a) / 2 + (z0 - zx) ** 2 / (2 * denom3);
    const ae = r0 + a - re;
    if (Math.abs(ae) > 1e-6) {
      const th3 = Math.asin(Math.max(-1, Math.min(1, (z0 - zx) / ae))) / (nb3 + 1);
      for (let i = 0; i < nb3; i++) {
        const th = (i + 1) * th3;
        pts.push([re + ae * Math.cos(th), z0 - ae * Math.sin(th)]);
      }
    }
  }

  pts.push([rx, zx]);

  const mr = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const mz = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  pts.sort((p, q) => Math.atan2(p[1] - mz, p[0] - mr) - Math.atan2(q[1] - mz, q[0] - mr));

  return { R: pts.map((p) => p[0]), Z: pts.map((p) => p[1]) };
}

// ── Coordinate mapping (equal aspect ratio) ───────────────────────────────────

const R_MIN = 1, R_MAX = 12, Z_MIN = -8, Z_MAX = 8;
const MARGIN = { l: 36, r: 8, t: 8, b: 28 };

// Compute the single pixel-per-metre scale and centred offsets that keep R and Z
// scaled identically, preventing physical distortion when the panel is resized.
function plotBounds(w: number, h: number) {
  const wa = w - MARGIN.l - MARGIN.r;
  const ha = h - MARGIN.t - MARGIN.b;
  const scale = Math.min(wa / (R_MAX - R_MIN), ha / (Z_MAX - Z_MIN));
  const pw = (R_MAX - R_MIN) * scale;
  const ph = (Z_MAX - Z_MIN) * scale;
  const left = MARGIN.l + (wa - pw) / 2;
  const top  = MARGIN.t + (ha - ph) / 2;
  return { left, top, pw, ph, scale };
}

function toSvgX(R: number, w: number, h: number) {
  const { left, scale } = plotBounds(w, h);
  return left + (R - R_MIN) * scale;
}
function toSvgY(Z: number, w: number, h: number) {
  const { top, scale } = plotBounds(w, h);
  return top + (Z_MAX - Z) * scale;
}
function fromSvgX(x: number, w: number, h: number) {
  const { left, scale } = plotBounds(w, h);
  return R_MIN + (x - left) / scale;
}
function fromSvgY(y: number, w: number, h: number) {
  const { top, scale } = plotBounds(w, h);
  return Z_MAX - (y - top) / scale;
}

// ── Geometric handles for parameterised mode ──────────────────────────────────

interface ParamHandle {
  id: string;
  label: string;
  color: string;
  R: number;
  Z: number;
  // Which params this handle controls and in which direction
  params: Array<{ name: string; axis: "R" | "Z" | "RZ" }>;
}

function getParamHandles(pv: Record<string, number>): ParamHandle[] {
  const kappa = pv.kappa ?? 1.8, delta = pv.delta ?? 0.43, a = pv.a ?? 1.9;
  const R0 = pv.center_r ?? 6.2, Z0 = pv.center_z ?? 0.545;
  const rx = pv.rx ?? 5.089, zx = pv.zx ?? -3.346;
  const da = Math.asin(Math.max(-0.99, Math.min(0.99, delta)));

  return [
    // Top of plasma — dragging Z changes kappa, dragging R changes delta
    // (the top point sits at R = R0 − a·δ, Z = Z0 + a·κ)
    {
      id: "top",
      label: "κ/δ",
      color: "#4f8ef7",
      R: R0 + a * Math.cos(Math.PI / 2 + da * Math.sin(Math.PI / 2)),
      Z: Z0 + kappa * a,
      params: [{ name: "kappa", axis: "Z" }, { name: "delta", axis: "R" }],
    },
    // Outer midplane — dragging R changes a
    {
      id: "outer",
      label: "a",
      color: "#3ddc84",
      R: R0 + a,
      Z: Z0,
      params: [{ name: "a", axis: "R" }],
    },
    // Inner midplane — dragging R changes a (mirrored)
    {
      id: "inner",
      label: "a",
      color: "#7c5cfc",
      R: R0 - a,
      Z: Z0,
      params: [{ name: "a", axis: "R" }],
    },
    // Center — dragging moves R0,Z0
    {
      id: "center",
      label: "R₀Z₀",
      color: "#f59e0b",
      R: R0,
      Z: Z0,
      params: [{ name: "center_r", axis: "R" }, { name: "center_z", axis: "Z" }],
    },
    // X-point
    {
      id: "xpoint",
      label: "Rₓ Zₓ",
      color: "#ff5370",
      R: rx,
      Z: zx,
      params: [{ name: "rx", axis: "R" }, { name: "zx", axis: "Z" }],
    },
  ];
}

// ── Machine geometry paths ────────────────────────────────────────────────────

function machinePaths(geo: MachineGeometries, w: number, h: number) {
  const paths: { d: string; stroke: string; width: number }[] = [];

  const toPath = (r: number[], z: number[]) =>
    r.map((rv, i) => `${i === 0 ? "M" : "L"} ${toSvgX(rv, w, h)} ${toSvgY(z[i], w, h)}`).join(" ");

  for (const u of geo.vacuum_vessel) paths.push({ d: toPath(u.r, u.z), stroke: "#3a3f5c", width: 1.2 });
  for (const u of geo.wall_limiter) paths.push({ d: toPath(u.r, u.z), stroke: "#555e7e", width: 1.5 });
  for (const c of geo.coil_rectangles) {
    const r = [c.r0, c.r1, c.r1, c.r0, c.r0];
    const z = [c.z0, c.z0, c.z1, c.z1, c.z0];
    paths.push({ d: toPath(r, z), stroke: "#64748b", width: 1 });
  }
  for (const c of geo.coil_paths) paths.push({ d: toPath(c.r, c.z), stroke: "#64748b", width: 1 });
  return paths;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  mode: "params" | "gaps";
  machineGeometries: MachineGeometries | null;
  niceResult: TimestepResult | null;
  paramValues: Record<string, number>;
  gaps: GapDefinition[];
  yamlContent: string;
  currentTime: number;
  /** Called once per drag with all changed params, so multi-param handles apply atomically */
  onParamChange: (updates: Record<string, number>) => void;
  /** Show drag handles for editing the shape (off by default) */
  editable?: boolean;
}

interface DragState {
  handleId: string;
  startR: number;
  startZ: number;
  startParamValues: Record<string, number>;
  currentR: number;
  currentZ: number;
}

const HANDLE_R = 7;

export function ShapeSvgView({ mode, machineGeometries, niceResult, paramValues, gaps, yamlContent, currentTime, onParamChange, editable = false }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({ w: 400, h: 500 });
  const [drag, setDrag] = useState<DragState | null>(null);
  const [liveParams, setLiveParams] = useState<Record<string, number>>({});
  const liveRef = useRef<Record<string, number>>({});
  useEffect(() => { liveRef.current = liveParams; }, [liveParams]);

  // Clear live overrides when the backing paramValues update (after async YAML parse),
  // preventing snap-back from liveParams being cleared before shapePreviewData settles.
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return; }
    setLiveParams({});
  }, [paramValues]);

  // Resize observer
  useEffect(() => {
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setSize({ w: width, h: height });
    });
    if (svgRef.current?.parentElement) obs.observe(svgRef.current.parentElement);
    return () => obs.disconnect();
  }, []);

  const { w, h } = size;

  // Merged params (live overrides paramValues during drag)
  const pv = { ...paramValues, ...liveParams };

  // Build outline
  const kappa = pv.kappa ?? 1.8, delta = pv.delta ?? 0.43, a = pv.a ?? 1.9;
  const R0 = pv.center_r ?? 6.2, Z0 = pv.center_z ?? 0.545;
  const rx = pv.rx ?? 5.089, zx = pv.zx ?? -3.346;

  const { R: oR, Z: oZ } = mode === "params"
    ? computeOutlineFromParams(a, R0, Z0, kappa, delta, rx, zx)
    : { R: [], Z: [] };

  // Gap mode outline from gap r_sep/z_sep points
  const gapOutlineR = mode === "gaps" ? gaps.map((g) => {
    const val = pv[`gap_${g.name}`] ?? g.value;
    return g.r + val * Math.cos(-g.angle);
  }) : [];
  const gapOutlineZ = mode === "gaps" ? gaps.map((g) => {
    const val = pv[`gap_${g.name}`] ?? g.value;
    return g.z + val * Math.sin(-g.angle);
  }) : [];

  // Outline SVG path
  const outlineR = mode === "params" ? oR : gapOutlineR;
  const outlineZ = mode === "params" ? oZ : gapOutlineZ;
  const outlinePath = outlineR.length
    ? outlineR.map((rv, i) => `${i === 0 ? "M" : "L"} ${toSvgX(rv, w, h)} ${toSvgY(outlineZ[i], w, h)}`).join(" ") + " Z"
    : "";

  // Handles
  const paramHandles = mode === "params" ? getParamHandles(pv) : [];

  // Machine geometry paths (static)
  const geoLines = machineGeometries ? machinePaths(machineGeometries, w, h) : [];

  // ── Mouse drag ───────────────────────────────────────────────────────────
  const startDrag = useCallback((e: React.MouseEvent, handleId: string) => {
    e.preventDefault(); e.stopPropagation();
    const svg = svgRef.current!;
    const rect = svg.getBoundingClientRect();
    const svgX = (e.clientX - rect.left) * (w / rect.width);
    const svgY = (e.clientY - rect.top) * (h / rect.height);
    const startR = fromSvgX(svgX, w, h), startZ = fromSvgY(svgY, w, h);
    setDrag({ handleId, startR, startZ, startParamValues: { ...paramValues }, currentR: startR, currentZ: startZ });
    setLiveParams({});
  }, [paramValues, w, h]);

  useEffect(() => {
    if (!drag) return;
    const onMove = (e: MouseEvent) => {
      const svg = svgRef.current!;
      const rect = svg.getBoundingClientRect();
      const svgX = (e.clientX - rect.left) * (w / rect.width);
      const svgY = (e.clientY - rect.top) * (h / rect.height);
      const curR = fromSvgX(svgX, w, h), curZ = fromSvgY(svgY, w, h);
      const dR = curR - drag.startR, dZ = curZ - drag.startZ;

      if (mode === "params") {
        const handle = paramHandles.find((ph) => ph.id === drag.handleId);
        if (!handle) return;
        const updates: Record<string, number> = {};
        for (const { name, axis } of handle.params) {
          const orig = drag.startParamValues[name] ?? paramValues[name] ?? 0;
          if (axis === "R") updates[name] = orig + dR;
          else if (axis === "Z") updates[name] = orig + dZ;
        }
        if (drag.handleId === "top") {
          // κ and δ are normalised by the minor radius: the top point is at
          // (R0 − a·δ, Z0 + a·κ), so a drag of (dR, dZ) metres maps to
          // dκ = dZ/a and dδ = −dR/a.
          const aVal = Math.max(0.1, drag.startParamValues.a ?? paramValues.a ?? 1.9);
          const origK = drag.startParamValues.kappa ?? paramValues.kappa ?? 1.8;
          const origD = drag.startParamValues.delta ?? paramValues.delta ?? 0.43;
          updates.kappa = Math.max(0.5, origK + dZ / aVal);
          updates.delta = Math.max(-0.95, Math.min(0.95, origD - dR / aVal));
        }
        if (drag.handleId === "outer") {
          const origA = drag.startParamValues.a ?? paramValues.a ?? 1.9;
          updates.a = Math.max(0.1, origA + dR);
        }
        if (drag.handleId === "inner") {
          const origA = drag.startParamValues.a ?? paramValues.a ?? 1.9;
          updates.a = Math.max(0.1, origA - dR);
        }
        setLiveParams(updates);
      } else {
        const gapName = drag.handleId;
        const gdef = gaps.find((g) => g.name === gapName);
        if (!gdef) return;
        const dirR = Math.cos(-gdef.angle), dirZ = Math.sin(-gdef.angle);
        const origVal = drag.startParamValues[`gap_${gapName}`] ?? gdef.value;
        const delta = dR * dirR + dZ * dirZ;
        setLiveParams({ [`gap_${gapName}`]: Math.max(0, origVal + delta) });
      }
    };

    const onUp = () => {
      const live = liveRef.current;
      if (Object.keys(live).length) onParamChange(live);
      setDrag(null);
      // liveParams intentionally NOT cleared here — the useEffect[paramValues] does it
      // once shapePreviewData settles after the async YAML parse, avoiding snap-back.
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [drag, mode, paramHandles, gaps, paramValues, onParamChange, w, h]);

  // ── Axis ticks ───────────────────────────────────────────────────────────
  const rTicks = [2, 4, 6, 8, 10];
  const zTicks = [-6, -4, -2, 0, 2, 4, 6];

  const bounds = plotBounds(w, h);

  return (
    <svg
      ref={svgRef}
      width={w}
      height={h}
      style={{ width: "100%", height: "100%", display: "block", cursor: drag ? "crosshair" : "default" }}
    >
      {/* Background — only the equal-aspect data rectangle */}
      <rect x={bounds.left} y={bounds.top} width={bounds.pw} height={bounds.ph} fill="var(--bg)" />

      {/* Grid */}
      {rTicks.map((rv) => {
        const x = toSvgX(rv, w, h);
        return (
          <g key={`rg${rv}`}>
            <line x1={x} y1={bounds.top} x2={x} y2={bounds.top + bounds.ph} stroke="var(--border)" strokeWidth={0.5} strokeDasharray="3 4" opacity={0.5} />
            <text x={x} y={bounds.top + bounds.ph + 14} textAnchor="middle" fontSize={9} fill="var(--text-muted)" fontFamily="monospace">{rv}</text>
          </g>
        );
      })}
      {zTicks.map((zv) => {
        const y = toSvgY(zv, w, h);
        return (
          <g key={`zg${zv}`}>
            <line x1={bounds.left} y1={y} x2={bounds.left + bounds.pw} y2={y} stroke="var(--border)" strokeWidth={0.5} strokeDasharray="3 4" opacity={0.5} />
            <text x={bounds.left - 4} y={y + 4} textAnchor="end" fontSize={9} fill="var(--text-muted)" fontFamily="monospace">{zv}</text>
          </g>
        );
      })}
      <text x={bounds.left + bounds.pw / 2} y={bounds.top + bounds.ph + 26} textAnchor="middle" fontSize={10} fill="var(--text-muted)">R [m]</text>
      <text x={8} y={bounds.top + bounds.ph / 2} textAnchor="middle" fontSize={10} fill="var(--text-muted)" transform={`rotate(-90,8,${bounds.top + bounds.ph / 2})`}>Z [m]</text>

      {/* Machine geometry */}
      {geoLines.map((l, i) => (
        <path key={i} d={l.d} fill="none" stroke={l.stroke} strokeWidth={l.width} />
      ))}

      {/* NICE equilibrium result */}
      {niceResult?.status === "success" && (() => {
        const psiValues = niceResult.contours.map((c) => c.psi);
        const minPsi = Math.min(...psiValues), maxPsi = Math.max(...psiValues);
        const psiRange = maxPsi - minPsi || 1;
        return (
          <g>
            {niceResult.contours.map((seg, ci) => {
              const norm = (seg.psi - minPsi) / psiRange;
              const r = Math.round(68 + norm * (253 - 68));
              const g2 = Math.round(1 + norm * (231 - 1));
              const b = Math.round(84 + norm * (37 - 84));
              const pts = seg.x.map((rx, i) => `${toSvgX(rx, w, h)},${toSvgY(seg.y[i], w, h)}`).join(" ");
              return <polyline key={ci} points={pts} fill="none" stroke={`rgb(${r},${g2},${b})`} strokeWidth={0.8} opacity={0.7} />;
            })}
            {niceResult.separatrix_r.length > 0 && (
              <polyline
                points={[...niceResult.separatrix_r, niceResult.separatrix_r[0]].map((rx, i) =>
                  `${toSvgX(rx, w, h)},${toSvgY(([...niceResult.separatrix_z, niceResult.separatrix_z[0]])[i], w, h)}`
                ).join(" ")}
                fill="none" stroke="#ff5370" strokeWidth={2}
              />
            )}
            {niceResult.o_points.map((p, i) => (
              <circle key={`o${i}`} cx={toSvgX(p.r, w, h)} cy={toSvgY(p.z, w, h)} r={5}
                fill="none" stroke="#fff" strokeWidth={1.5} />
            ))}
            {niceResult.x_points.map((p, i) => {
              const cx = toSvgX(p.r, w, h), cy = toSvgY(p.z, w, h), d = 5;
              return (
                <g key={`x${i}`}>
                  <line x1={cx - d} y1={cy - d} x2={cx + d} y2={cy + d} stroke="#fff" strokeWidth={1.5} />
                  <line x1={cx + d} y1={cy - d} x2={cx - d} y2={cy + d} stroke="#fff" strokeWidth={1.5} />
                </g>
              );
            })}
          </g>
        );
      })()}

      {/* Input plasma outline (dashed in gap mode — it's the desired boundary, not a parameterised shape) */}
      {outlinePath && (
        <path d={outlinePath} fill="rgba(79,142,247,0.08)" stroke="#4f8ef7" strokeWidth={2}
          strokeDasharray={mode === "gaps" ? "7 5" : undefined} />
      )}

      {/* Gap points (gap mode) */}
      {mode === "gaps" && gaps.map((g) => {
        const gval = pv[`gap_${g.name}`] ?? g.value;
        const gR = g.r + gval * Math.cos(-g.angle);
        const gZ = g.z + gval * Math.sin(-g.angle);
        const isDragging = drag?.handleId === g.name;
        return (
          <g key={g.name}>
            <line
              x1={toSvgX(g.r, w, h)} y1={toSvgY(g.z, w, h)}
              x2={toSvgX(gR, w, h)} y2={toSvgY(gZ, w, h)}
              stroke="#4f8ef7" strokeWidth={1} opacity={0.4} strokeDasharray="3 2"
            />
            <circle cx={toSvgX(g.r, w, h)} cy={toSvgY(g.z, w, h)} r={2} fill="#64748b" />
            {editable ? (
              <circle
                cx={toSvgX(gR, w, h)} cy={toSvgY(gZ, w, h)}
                r={isDragging ? HANDLE_R + 2 : HANDLE_R}
                fill={isDragging ? "#4f8ef7" : "var(--bg2)"}
                stroke="#4f8ef7" strokeWidth={2}
                style={{ cursor: "ns-resize" }}
                onMouseDown={(e) => startDrag(e, g.name)}
              />
            ) : (
              <circle cx={toSvgX(gR, w, h)} cy={toSvgY(gZ, w, h)} r={3} fill="#4f8ef7" />
            )}
            <text x={toSvgX(gR, w, h) + HANDLE_R + 3} y={toSvgY(gZ, w, h) + 4} fontSize={9} fill="#4f8ef7" fontFamily="monospace">
              {g.name}
            </text>
          </g>
        );
      })}

      {/* Param handles (params mode, only when editing is enabled) */}
      {mode === "params" && editable && paramHandles.map((ph) => {
        const isDragging = drag?.handleId === ph.id;
        const cx = toSvgX(ph.R, w, h), cy = toSvgY(ph.Z, w, h);
        const cursor = ph.params.some((p) => p.axis === "R") && ph.params.some((p) => p.axis === "Z")
          ? "move" : ph.params[0]?.axis === "R" ? "ew-resize" : "ns-resize";
        return (
          <g key={ph.id}>
            <circle cx={cx} cy={cy} r={isDragging ? HANDLE_R + 3 : HANDLE_R + 1} fill="none" stroke={ph.color} strokeWidth={1} opacity={0.4} />
            <circle
              cx={cx} cy={cy} r={isDragging ? HANDLE_R + 1 : HANDLE_R}
              fill={isDragging ? ph.color : "var(--bg2)"} stroke={ph.color} strokeWidth={2}
              style={{ cursor }}
              onMouseDown={(e) => startDrag(e, ph.id)}
            />
            <text x={cx + HANDLE_R + 3} y={cy + 4} fontSize={9} fill={ph.color} fontFamily="monospace">{ph.label}</text>
          </g>
        );
      })}

      {/* Axis border */}
      <rect x={bounds.left} y={bounds.top} width={bounds.pw} height={bounds.ph} fill="none" stroke="var(--border)" strokeWidth={1} />
    </svg>
  );
}
