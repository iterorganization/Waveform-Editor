import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "../../store";
import type { GapDefinition, TendencyInfo } from "../../types";
import { ComparisonPanel } from "../comparison/ComparisonPanel";
import { WaveformViewer } from "../waveform-viewer/WaveformViewer";
import { ShapeSvgView } from "./ShapeSvgView";

// ── Shape waveform names ───────────────────────────────────────────────────────

export const SHAPE_PARAMS = [
  { name: "kappa",    label: "κ",   fullLabel: "Elongation κ",         unit: "",  color: "#4f8ef7" },
  { name: "delta",    label: "δ",   fullLabel: "Triangularity δ",       unit: "",  color: "#7c5cfc" },
  { name: "a",        label: "a",   fullLabel: "Minor radius a",        unit: "m", color: "#3ddc84" },
  { name: "center_r", label: "R₀",  fullLabel: "Center radius R₀",      unit: "m", color: "#f97316" },
  { name: "center_z", label: "Z₀",  fullLabel: "Center height Z₀",      unit: "m", color: "#f59e0b" },
  { name: "rx",       label: "Rₓ",  fullLabel: "X-point radius Rₓ",     unit: "m", color: "#ff5370" },
  { name: "zx",       label: "Zₓ",  fullLabel: "X-point height Zₓ",     unit: "m", color: "#f06292" },
] as const;

// ── Smart YAML update ─────────────────────────────────────────────────────────

function fmtN(v: number): string {
  if (!isFinite(v)) return "0";
  if (Number.isInteger(v) && Math.abs(v) < 1e6) return String(v);
  const abs = Math.abs(v);
  if (abs === 0) return "0";
  if (abs >= 1e5 || (abs < 1e-3 && abs > 0)) return v.toPrecision(5);
  return parseFloat(v.toPrecision(6)).toString();
}

function rewriteLine(line: string, toRemove: string[], toAdd: [string, number][]): string {
  const m = line.match(/^(\s*-\s*\{)(.+?)(\}\s*)$/);
  if (!m) return line;
  const [, prefix, content, suffix] = m;
  const re = /(\w+)\s*:\s*([^,}]+)/g;
  let match: RegExpExecArray | null;
  const pairs: [string, string][] = [];
  while ((match = re.exec(content)) !== null) pairs.push([match[1], match[2].trim()]);
  let result = pairs.filter(([k]) => !toRemove.includes(k));
  for (const [k, v] of toAdd) {
    const fmt = fmtN(v);
    const idx = result.findIndex(([rk]) => rk === k);
    if (idx >= 0) result[idx] = [k, fmt]; else result.push([k, fmt]);
  }
  return `${prefix}${result.map(([k, v]) => `${k}: ${v}`).join(", ")}${suffix}`;
}

export interface SampledWaveform {
  times: number[];
  values: number[];
}

/** Linear interpolation of the rendered waveform at time t */
function sampleAt(s: SampledWaveform | undefined, t: number): number | null {
  if (!s || !s.times.length) return null;
  const { times, values } = s;
  if (t <= times[0]) return values[0];
  if (t >= times[times.length - 1]) return values[values.length - 1];
  for (let i = 1; i < times.length; i++) {
    if (times[i] >= t) {
      const f = (t - times[i - 1]) / (times[i] - times[i - 1] || 1);
      return values[i - 1] + f * (values[i] - values[i - 1]);
    }
  }
  return values[values.length - 1];
}

/** Extend a waveform past its end: append a linear tendency from the last
 *  value to [newValue], ending at [time]. */
function appendLinearTendency(
  yamlContent: string,
  last: TendencyInfo,
  time: number,
  newValue: number,
  sampled?: SampledWaveform,
): string {
  const lastValue = sampleAt(sampled, last.end_time)
    ?? last.params.to ?? last.params.value ?? newValue;
  const lines = yamlContent.split("\n");
  const lastLine = lines[last.line_number] ?? "";
  const indent = lastLine.match(/^(\s*-\s*)/)?.[1] ?? "  - ";
  const dashIndent = lastLine.match(/^(\s*)-/)?.[1]?.length ?? 2;

  // Insert after the last tendency entry, skipping any continuation lines of
  // a multi-line entry (e.g. a repeat block's nested waveform)
  let insertAt = last.line_number + 1;
  while (insertAt < lines.length) {
    const l = lines[insertAt];
    if (l.trim() === "") break; // blank line separates sections — stop
    const ws = l.match(/^(\s*)/)?.[1].length ?? 0;
    if (ws <= dashIndent) break; // next sibling item or next mapping key
    insertAt++;
  }

  lines.splice(insertAt, 0,
    `${indent}{type: linear, from: ${fmtN(lastValue)}, to: ${fmtN(newValue)}, duration: ${fmtN(time - last.end_time)}}`);
  return lines.join("\n");
}

export function smartUpdateYaml(
  yamlContent: string,
  tendencies: TendencyInfo[],
  time: number,
  newValue: number,
  sampled?: SampledWaveform,
): string {
  if (!tendencies.length) return yamlContent;
  // Find the tendency covering [time]
  let tdIdx = tendencies.findIndex(
    (td) => td.start_time <= time + 1e-9 && td.end_time >= time - 1e-9
  );
  if (tdIdx < 0) {
    // The scrub time lies outside this waveform's own range (the timeline
    // spans the longest waveform).
    const first = tendencies[0];
    const last = tendencies[tendencies.length - 1];
    if (time > last.end_time + 1e-3) {
      // Beyond the end: extend the waveform with a linear tendency from its
      // last value to the new value at the selected time.
      return appendLinearTendency(yamlContent, last, time, newValue, sampled);
    } else if (time > last.end_time) {
      tdIdx = tendencies.length - 1;
      time = last.end_time;
    } else if (time < first.start_time) {
      // Before the start: adjust the initial value
      tdIdx = 0;
      time = first.start_time;
    } else {
      return yamlContent; // inside a gap between tendencies — nothing to edit
    }
  }
  const td = tendencies[tdIdx];
  const lines = yamlContent.split("\n");
  const dur = td.end_time - td.start_time;
  const frac = dur > 0 ? (time - td.start_time) / dur : 0;
  const atStart = frac <= 0.03, atEnd = frac >= 0.97;

  const indent = lines[td.line_number]?.match(/^(\s*-\s*)/)?.[1] ?? "  - ";
  const mkLine = (type: string, pairs: [string, number][]) =>
    `${indent}{type: ${type}, ${pairs.map(([k, v]) => `${k}: ${fmtN(v)}`).join(", ")}}`;

  if (td.type === "constant") {
    // Keep the boundary values, bend to the new value at [time] and back:
    // one linear when editing at an edge, two linears when editing mid-tendency.
    const v0 = td.params.value ?? sampleAt(sampled, td.start_time) ?? newValue;
    if (atStart) {
      lines.splice(td.line_number, 1,
        mkLine("linear", [["from", newValue], ["to", v0], ["duration", dur]]));
    } else if (atEnd) {
      lines.splice(td.line_number, 1,
        mkLine("linear", [["from", v0], ["to", newValue], ["duration", dur]]));
    } else {
      lines.splice(td.line_number, 1,
        mkLine("linear", [["from", v0], ["to", newValue], ["duration", time - td.start_time]]),
        mkLine("linear", [["from", newValue], ["to", v0], ["duration", td.end_time - time]]));
    }
  } else if (td.type === "linear" || td.type === "smooth") {
    // Preserve both endpoints (and thus continuity with neighbours); split at
    // [time] so the segment passes through the new value there.
    const from = td.params.from ?? sampleAt(sampled, td.start_time) ?? newValue;
    const to = td.params.to ?? sampleAt(sampled, td.end_time) ?? newValue;
    if (atStart) {
      lines[td.line_number] = rewriteLine(lines[td.line_number], [], [["from", newValue]]);
    } else if (atEnd) {
      lines[td.line_number] = rewriteLine(lines[td.line_number], [], [["to", newValue]]);
      // Cascade: if next tendency's explicit `from` matched the old `to`, update it too
      if (tdIdx + 1 < tendencies.length) {
        const next = tendencies[tdIdx + 1];
        if ("from" in next.params && Math.abs(next.params.from - to) < 1e-4) {
          lines[next.line_number] = rewriteLine(lines[next.line_number], [], [["from", newValue]]);
        }
      }
    } else {
      lines.splice(td.line_number, 1,
        mkLine(td.type, [["from", from], ["to", newValue], ["duration", time - td.start_time]]),
        mkLine(td.type, [["from", newValue], ["to", to], ["duration", td.end_time - time]]));
    }
  } else if (/^(sine|triangle|sawtooth|square)(-wave)?$/.test(td.type)) {
    // Scale the wave amplitude so it passes through the new value at [time].
    // Near a zero crossing amplitude has no leverage — shift the base instead.
    const hasMinMax = "min" in td.params || "max" in td.params;
    const base = td.params.base
      ?? (td.params.min != null && td.params.max != null ? (td.params.min + td.params.max) / 2 : 0);
    const amplitude = td.params.amplitude
      ?? (td.params.min != null && td.params.max != null ? (td.params.max - td.params.min) / 2 : 1);
    const oldValue = sampleAt(sampled, time);
    if (oldValue !== null) {
      const g = amplitude !== 0 ? (oldValue - base) / amplitude : 0; // wave phase position in [-1, 1]
      const [newBase, newAmp] = Math.abs(g) >= 0.15
        ? [base, (newValue - base) / g]
        : [base + (newValue - oldValue), amplitude];
      // Normalize min/max style to base/amplitude so a single consistent rewrite works
      lines[td.line_number] = rewriteLine(
        lines[td.line_number],
        hasMinMax ? ["min", "max"] : [],
        [["base", newBase], ["amplitude", newAmp]],
      );
    }
  } else if (td.type === "piecewise") {
    const times = [...(td.piecewise_times ?? [])];
    const values = [...(td.piecewise_values ?? [])];
    const existingIdx = times.findIndex((ti) => Math.abs(ti - time) < 0.02);
    if (existingIdx >= 0) {
      values[existingIdx] = newValue;
    } else {
      const insertIdx = times.findIndex((ti) => ti > time);
      if (insertIdx === -1) { times.push(time); values.push(newValue); }
      else { times.splice(insertIdx, 0, time); values.splice(insertIdx, 0, newValue); }
    }
    const lm = lines[td.line_number].match(/^(\s*-\s*\{)(.+?)(\}\s*)$/);
    if (lm) {
      const tStr = times.map(fmtN).join(", ");
      const vStr = values.map(fmtN).join(", ");
      lines[td.line_number] = `${lm[1]}type: piecewise, time: [${tStr}], value: [${vStr}]${lm[3]}`;
    }
  }
  // For other tendency types: no change (too complex to modify meaningfully)
  return lines.join("\n");
}

// ── Tiny inline sparkline (used inside a row button) ─────────────────────────

function MiniSparkline({ times, values, currentTime, color, tMin, tMax }: {
  times: number[]; values: number[]; currentTime: number; color: string;
  tMin: number; tMax: number;
}) {
  const w = 100, h = 40;
  const vMin = Math.min(...values), vMax = Math.max(...values);
  const tRange = tMax - tMin || 1;
  const vRange = vMax - vMin || 1;
  const sx = (t: number) => ((t - tMin) / tRange) * w;
  const sy = (v: number) => h - 3 - ((v - vMin) / vRange) * (h - 6);
  const pts = times.map((t, i) => `${sx(t)},${sy(values[i])}`).join(" ");
  const cx = sx(currentTime);
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      width="100%"
      height={h}
      style={{ display: "block" }}
    >
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} opacity={0.8} vectorEffect="non-scaling-stroke" />
      <line x1={cx} y1={0} x2={cx} y2={h} stroke={color} strokeWidth={1} opacity={0.55} strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

// ── Gap loader ────────────────────────────────────────────────────────────────

function GapLoader() {
  const { shapeGapUri, shapeGaps, loadShapeGaps, shapePreviewData, shapePreviewIndex, yamlContent, setYamlContent, parseCurrentYaml } = useStore();
  const [uri, setUri] = useState(shapeGapUri);
  const [time, setTime] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const currentTime = shapePreviewData?.times[shapePreviewIndex] ?? 0;

  const handleLoad = async () => {
    setLoading(true); setError("");
    const err = await loadShapeGaps(uri, time);
    setLoading(false);
    if (err) { setError(err); return; }
  };

  const handleCreateWaveforms = () => {
    if (!shapeGaps.length) return;
    // Add gap waveforms to YAML if not present
    let yaml = yamlContent;
    const hasGapGroup = yaml.includes("NICE Shape Gaps:");
    if (!hasGapGroup) {
      yaml += "\nNICE Shape Gaps:\n";
    }
    // Find which gaps don't have waveforms yet
    for (const gap of shapeGaps) {
      const wfName = `gap_${gap.name}`;
      if (!yaml.includes(`${wfName}:`)) {
        yaml += `  ${wfName}:\n  - {type: constant, value: ${fmtN(gap.value)}, duration: 100}\n`;
      }
    }
    setYamlContent(yaml);
    parseCurrentYaml();
  };

  return (
    <div className="se-gap-loader">
      <div className="se-gap-loader-row">
        <input
          className="se-text-input"
          placeholder="Equilibrium IDS URI (e.g. imas:hdf5:...)"
          value={uri}
          onChange={(e) => setUri(e.target.value)}
          style={{ flex: 1 }}
        />
        <input
          className="se-text-input"
          type="number"
          step="any"
          placeholder="Time"
          value={time}
          onChange={(e) => setTime(parseFloat(e.target.value) || 0)}
          style={{ width: 70 }}
          title="Time slice to load from IDS"
        />
        <button className="se-btn" onClick={handleLoad} disabled={!uri || loading}>
          {loading ? "…" : "Load"}
        </button>
      </div>
      {error && <div className="se-gap-error">{error}</div>}
      {shapeGaps.length > 0 && (
        <div className="se-gap-list">
          <div className="se-gap-list-header">
            {shapeGaps.length} gaps loaded
            <button className="se-btn se-btn-sm" onClick={handleCreateWaveforms}>
              Create waveforms
            </button>
          </div>
          {shapeGaps.map((g) => (
            <div key={g.name} className="se-gap-item">
              <span className="se-gap-name">{g.name}</span>
              <span className="se-gap-coords">r={fmtN(g.r)} z={fmtN(g.z)} α={fmtN(g.angle)}</span>
              <span className="se-gap-val">{fmtN(g.value)} m</span>
            </div>
          ))}
        </div>
      )}
      {!shapeGaps.length && (
        <div className="se-gap-hint">Load gaps from an equilibrium IDS, then click "Create waveforms" to add them to the YAML.</div>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function ShapeEditorPanel() {
  const {
    shapeEditorMode, setShapeEditorMode,
    shapeGaps,
    shapePreviewData, shapePreviewIndex,
    machineGeometries,
    results, currentResultIndex,
    yamlContent, setYamlContent, parseCurrentYaml,
    tendenciesCache, addTendencyWatch, removeTendencyWatch,
  } = useStore();

  const hasNice = results.length > 0;
  // currentResultIndex is derived from the scrub time (latest result at or
  // before it) — may be -1 when scrubbed before the first computed timestep.
  const niceResult = hasNice ? (results[currentResultIndex] ?? null) : null;

  // The timeline is always the full preview timeline; NICE results are an overlay.
  const currentTime = shapePreviewData?.times[shapePreviewIndex] ?? niceResult?.t ?? 0;

  // Which waveform is open in the inline editor (null = closed)
  const [selectedWaveform, setSelectedWaveform] = useState<string | null>(null);

  // Drag handles on the 2D shape view — off by default
  const [editShape, setEditShape] = useState(false);

  // Register which waveforms this panel needs tendencies for — the store keeps
  // them fresh in the same round trip as each YAML parse (no per-waveform calls).
  useEffect(() => {
    const names = shapeEditorMode === "params"
      ? SHAPE_PARAMS.map((p) => p.name)
      : shapeGaps.map((g) => `gap_${g.name}`);
    addTendencyWatch(names);
    return () => removeTendencyWatch(names);
  }, [shapeEditorMode, shapeGaps, addTendencyWatch, removeTendencyWatch]);

  const handleParamChange = useCallback(
    (updates: Record<string, number>) => {
      // Apply all edits of a drag against a single evolving YAML string.
      // Descending line order so a split (one line → two) can't shift the
      // line numbers of waveforms edited after it.
      const entries = Object.entries(updates)
        .filter(([name]) => tendenciesCache[name]?.length)
        .sort(([a], [b]) => (tendenciesCache[b][0].line_number - tendenciesCache[a][0].line_number));
      let yaml = yamlContent;
      for (const [paramName, newValue] of entries) {
        const sampled = shapePreviewData?.waveforms[paramName]
          ? { times: shapePreviewData.times, values: shapePreviewData.waveforms[paramName] }
          : undefined;
        yaml = smartUpdateYaml(yaml, tendenciesCache[paramName], currentTime, newValue, sampled);
      }
      if (yaml !== yamlContent) {
        setYamlContent(yaml);
        parseCurrentYaml();
      }
    },
    [tendenciesCache, yamlContent, currentTime, setYamlContent, parseCurrentYaml, shapePreviewData]
  );

  const paramValues = useMemo(() => {
    const pv: Record<string, number> = {};
    if (shapePreviewData) {
      // Desired shape at the current scrub time — browsable across the whole
      // timeline regardless of which timesteps NICE actually computed.
      for (const p of SHAPE_PARAMS) {
        const arr = shapePreviewData.waveforms[p.name];
        if (arr) pv[p.name] = arr[shapePreviewIndex] ?? 0;
      }
      for (const g of shapeGaps) {
        const wn = `gap_${g.name}`;
        const arr = shapePreviewData.waveforms[wn];
        if (arr) pv[wn] = arr[shapePreviewIndex] ?? g.value;
      }
    } else if (niceResult) {
      // No preview data (e.g. YAML parse failure) — fall back to the result's inputs
      for (const p of SHAPE_PARAMS) {
        const v = niceResult.input_values[p.name];
        if (v != null) pv[p.name] = v;
      }
    }
    return pv;
  }, [niceResult, shapePreviewData, shapePreviewIndex, shapeGaps]);

  // Rows to show in the right panel
  const inputRows: Array<{ name: string; label: string; color: string; unit: string }> =
    shapeEditorMode === "params"
      ? SHAPE_PARAMS.map((p) => ({ name: p.name, label: p.fullLabel, color: p.color, unit: p.unit }))
      : shapeGaps.map((g) => ({ name: `gap_${g.name}`, label: g.name, color: "#4f8ef7", unit: "m" }));

  // ── Resizable se-main split ──────────────────────────────────────────────────
  const [svgRatio, setSvgRatio] = useState(0.5);
  const seMainRef = useRef<HTMLDivElement>(null);
  const isResizingSe = useRef(false);
  const seResizeStartX = useRef(0);
  const seResizeStartRatio = useRef(0.5);

  const onSeResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizingSe.current = true;
    seResizeStartX.current = e.clientX;
    seResizeStartRatio.current = svgRatio;
  }, [svgRatio]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isResizingSe.current) return;
      const container = seMainRef.current;
      if (!container) return;
      const totalW = container.getBoundingClientRect().width;
      if (totalW === 0) return;
      const delta = e.clientX - seResizeStartX.current;
      setSvgRatio(Math.max(0.2, Math.min(0.8, seResizeStartRatio.current + delta / totalW)));
    };
    const onUp = () => { isResizingSe.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  // ── Vertical split: shape parameter cards / NICE results (default 50/50) ──
  const [inputsRatio, setInputsRatio] = useState(0.5);
  const resultsPanelRef = useRef<HTMLDivElement>(null);
  const isResizingV = useRef(false);
  const vResizeStartY = useRef(0);
  const vResizeStartRatio = useRef(0.5);

  const onVResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizingV.current = true;
    vResizeStartY.current = e.clientY;
    vResizeStartRatio.current = inputsRatio;
  }, [inputsRatio]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isResizingV.current) return;
      const container = resultsPanelRef.current;
      if (!container) return;
      const totalH = container.getBoundingClientRect().height;
      if (totalH === 0) return;
      const delta = e.clientY - vResizeStartY.current;
      setInputsRatio(Math.max(0.15, Math.min(0.85, vResizeStartRatio.current + delta / totalH)));
    };
    const onUp = () => { isResizingV.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  return (
    <div className="se-panel">
      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className="se-toolbar">
        <div className="se-toggle-group">
          <button
            className={`se-toggle-btn${shapeEditorMode === "params" ? " active" : ""}`}
            onClick={() => setShapeEditorMode("params")}
          >Parameterized</button>
          <button
            className={`se-toggle-btn${shapeEditorMode === "gaps" ? " active" : ""}`}
            onClick={() => setShapeEditorMode("gaps")}
          >Gaps</button>
        </div>
        <button
          className={`se-toggle-btn se-edit-toggle${editShape ? " active" : ""}`}
          onClick={() => setEditShape((v) => !v)}
          title={editShape ? "Disable shape editing handles" : "Enable shape editing handles"}
        >✎ Edit shape</button>
        <span className="se-time-chip">t = {currentTime.toFixed(3)} s</span>
      </div>

      {shapeEditorMode === "gaps" && <GapLoader />}

      <div className="se-main" ref={seMainRef}>
        {/* 2D SVG shape view */}
        <div className="se-svg-wrap" style={{ flex: svgRatio }}>
          <ShapeSvgView
            mode={shapeEditorMode}
            machineGeometries={machineGeometries}
            niceResult={niceResult}
            paramValues={paramValues}
            gaps={shapeGaps}
            yamlContent={yamlContent}
            currentTime={currentTime}
            onParamChange={handleParamChange}
            editable={editShape}
          />
        </div>

        <div className="se-resize-handle" onMouseDown={onSeResizeStart} />

        {/* Right side: waveform editor when open, otherwise input list + NICE results */}
        {selectedWaveform ? (
          <WaveformViewer
            inline
            forceName={selectedWaveform}
            onClose={() => setSelectedWaveform(null)}
            style={{ flex: 1 - svgRatio, minWidth: 0 }}
          />
        ) : (
        <div className="se-results-panel" style={{ flex: 1 - svgRatio }} ref={resultsPanelRef}>
          {/* Input waveform rows */}
          <div className="se-inputs-list" style={{ flex: hasNice ? inputsRatio : 1 }}>
            {inputRows.length === 0 && (
              <div className="se-inputs-empty">
                {shapeEditorMode === "params"
                  ? "Define shape waveforms in the YAML."
                  : "Load gaps from an IDS above."}
              </div>
            )}
            {(() => {
              const allTimes = shapePreviewData?.times ?? [];
              const tMin = allTimes[0] ?? 0;
              const tMax = allTimes[allTimes.length - 1] ?? 1;
              return inputRows.map(({ name, label, color, unit }) => {
                const values = shapePreviewData?.waveforms[name];
                const curVal = paramValues[name] ?? null;
                const isSelected = selectedWaveform === name;
                return (
                  <button
                    key={name}
                    className={`se-wf-row${isSelected ? " selected" : ""}${values ? "" : " missing"}`}
                    onClick={() => setSelectedWaveform(isSelected ? null : name)}
                    title={values ? `Edit ${name}` : `${name} not in YAML`}
                  >
                    <div className="se-wf-row-header">
                      <span className="se-wf-dot" style={{ background: color }} />
                      <span className="se-wf-label">{label}</span>
                      {curVal !== null && (
                        <span className="se-wf-val">{fmtN(curVal)}{unit ? ` ${unit}` : ""}</span>
                      )}
                    </div>
                    {values && allTimes.length > 1 && (
                      <MiniSparkline times={allTimes} values={values} currentTime={currentTime} color={color} tMin={tMin} tMax={tMax} />
                    )}
                  </button>
                );
              });
            })()}
          </div>

          {/* NICE comparison charts */}
          {hasNice && (
            <>
              <div
                className="se-results-divider se-results-divider--draggable"
                onMouseDown={onVResizeStart}
                title="Drag to resize"
              >NICE results — {results.length} timesteps</div>
              <div className="se-results-charts" style={{ flex: 1 - inputsRatio }}>
                <ComparisonPanel />
              </div>
            </>
          )}
        </div>
        )}
      </div>

    </div>
  );
}
