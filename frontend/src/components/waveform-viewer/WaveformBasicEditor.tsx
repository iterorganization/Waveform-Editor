import { useState, useCallback, useRef, useEffect } from "react";
import type { TendencyInfo } from "../../types";

// ── Constants ─────────────────────────────────────────────────────────────────

const COLORS = [
  "#4f8ef7", "#7c5cfc", "#2dd4bf", "#f97316",
  "#3ddc84", "#f59e0b", "#f472b6", "#e879f9",
];

export const TENDENCY_CATALOG = [
  { type: "constant",      label: "Constant",      icon: "━",  group: "Basic"    },
  { type: "linear",        label: "Linear",         icon: "╱",  group: "Basic"    },
  { type: "smooth",        label: "Smooth",         icon: "⌒",  group: "Basic"    },
  { type: "sine-wave",     label: "Sine",           icon: "∿",  group: "Periodic" },
  { type: "square-wave",   label: "Square",         icon: "⊓",  group: "Periodic" },
  { type: "triangle-wave", label: "Triangle",       icon: "∧",  group: "Periodic" },
  { type: "sawtooth-wave", label: "Sawtooth",       icon: "⋱",  group: "Periodic" },
  { type: "piecewise",     label: "Piecewise",      icon: "◆",  group: "Complex"  },
  { type: "repeat",        label: "Repeat",         icon: "↺",  group: "Complex"  },
] as const;

const COMPLEX_TYPES = new Set(["piecewise", "repeat"]);
const PERIODIC_TYPES = new Set(["sine-wave", "square-wave", "triangle-wave", "sawtooth-wave"]);

// Canonical display order for params
const FIELD_ORDER = [
  "value", "from", "to", "rate",
  "start", "end",
  "base", "min", "max", "amplitude",
  "frequency", "period", "phase",
  "duration",
];

const FIELD_LABELS: Record<string, string> = {
  value: "Value", from: "From", to: "To", rate: "Rate",
  start: "Start", end: "End",
  base: "Center", min: "Min", max: "Max",
  amplitude: "Amplitude", frequency: "Frequency",
  period: "Period", phase: "Phase", duration: "Duration",
};

const FIELD_UNITS: Record<string, string> = {
  frequency: "Hz", period: "s", phase: "rad",
  start: "s", end: "s", duration: "s",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function getTendencyEndValue(td: TendencyInfo): number {
  const p = td.params;
  const dur = td.end_time - td.start_time;
  switch (td.type) {
    case "constant": return p.value ?? 0;
    case "linear":
    case "smooth":   return p.to ?? p.from ?? 0;
    case "sine-wave": {
      const base = p.base ?? 0, amp = p.amplitude ?? 0;
      const freq = p.frequency ?? (p.period ? 1 / p.period : 0);
      const phase = p.phase ?? 0;
      return base + amp * Math.sin(2 * Math.PI * freq * dur + phase);
    }
    case "triangle-wave": {
      const base = p.base ?? 0, amp = p.amplitude ?? 0;
      const period = p.period ?? (p.frequency ? 1 / p.frequency : dur || 1);
      const phase = p.phase ?? 0;
      const theta = 2 * Math.PI / period * dur + phase - Math.PI / 2;
      const tn = ((theta / Math.PI) % 2 + 2) % 2;
      return base + amp * (2 * Math.abs(tn - 1) - 1);
    }
    case "sawtooth-wave": {
      const base = p.base ?? 0, amp = p.amplitude ?? 0;
      const period = p.period ?? (p.frequency ? 1 / p.frequency : dur || 1);
      const phase = p.phase ?? 0;
      const raw = dur + period / 2 + phase * period / (2 * Math.PI);
      const tc = ((raw % period) + period) % period;
      return base + amp * ((tc / period) * 2 - 1);
    }
    case "square-wave": {
      const base = p.base ?? 0, amp = p.amplitude ?? 0;
      const period = p.period ?? (p.frequency ? 1 / p.frequency : dur || 1);
      const phase = p.phase ?? 0;
      const raw = dur + phase * period / (2 * Math.PI);
      const tc = ((raw % period) + period) % period;
      return base + amp * (tc < period / 2 ? 1 : -1);
    }
    default: return p.to ?? p.value ?? p.base ?? p.max ?? 0;
  }
}

function fmtNum(v: number): string {
  if (!isFinite(v)) return "0";
  if (Number.isInteger(v) && Math.abs(v) < 1e6) return String(v);
  const abs = Math.abs(v);
  if (abs === 0) return "0";
  if (abs >= 1e5 || (abs < 1e-3 && abs > 0)) return v.toPrecision(4);
  return parseFloat(v.toPrecision(6)).toString();
}

function getDefaultParams(type: string, prevEnd = 0): Record<string, number> {
  switch (type) {
    case "constant":      return { value: prevEnd, duration: 10 };
    case "linear":        return { from: prevEnd, to: prevEnd, duration: 10 };
    case "smooth":        return { from: prevEnd, to: prevEnd, duration: 10 };
    case "sine-wave":
    case "square-wave":
    case "triangle-wave":
    case "sawtooth-wave": return { base: prevEnd, amplitude: 1, frequency: 1, duration: 10 };
    default:              return { duration: 10 };
  }
}

function serializeTendencyLine(type: string, params: Record<string, number>): string {
  const parts = [`type: ${type}`];
  const included = new Set<string>();
  for (const f of FIELD_ORDER) {
    if (f in params) { parts.push(`${f}: ${fmtNum(params[f])}`); included.add(f); }
  }
  for (const [k, v] of Object.entries(params)) {
    if (!included.has(k)) parts.push(`${k}: ${fmtNum(v)}`);
  }
  return `- {${parts.join(", ")}}`;
}

// Find the waveform section line range in the full YAML
function findSectionBounds(yaml: string, name: string): { startLine: number; endLine: number; indent: string } | null {
  const lines = yaml.split("\n");
  const esc = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`^(\\s+)(${esc}):\\s*$`);
  let startLine = -1, indent = "";
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(re);
    if (m) { startLine = i; indent = m[1]; break; }
  }
  if (startLine === -1) return null;
  const indentLen = indent.length;
  let endLine = startLine + 1;
  while (endLine < lines.length) {
    const raw = lines[endLine];
    const trimmed = raw.trimStart();
    if (trimmed === "") { endLine++; continue; }
    if (raw.length - trimmed.length <= indentLen && /^\S+:/.test(trimmed)) break;
    endLine++;
  }
  return { startLine, endLine, indent };
}

// ── Representation picker ─────────────────────────────────────────────────────

// Rewrite an inline YAML tendency line: remove keys and add/update keys.
// Preserves the line's indentation and "- {}" wrapper; sorts output by FIELD_ORDER.
function rewriteTendencyLine(
  line: string,
  toRemove: string[],
  toAdd: Array<[string, number]>,
): string {
  const m = line.match(/^(\s*-\s*\{)(.+?)(\}\s*)$/);
  if (!m) return line;
  const [, prefix, content, suffix] = m;

  const pairs: [string, string][] = [];
  const re = /(\w+)\s*:\s*([^,}]+)/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(content)) !== null) {
    pairs.push([match[1], match[2].trim()]);
  }

  let result = pairs.filter(([k]) => !toRemove.includes(k));
  for (const [k, v] of toAdd) {
    const formatted = fmtNum(v);
    const idx = result.findIndex(([rk]) => rk === k);
    if (idx >= 0) result[idx] = [k, formatted];
    else result.push([k, formatted]);
  }

  // Sort by canonical order (type first, then FIELD_ORDER, unknowns at end)
  const ORDER = ["type", ...FIELD_ORDER];
  result.sort((a, b) => {
    const ai = ORDER.indexOf(a[0]), bi = ORDER.indexOf(b[0]);
    if (ai < 0 && bi < 0) return 0;
    if (ai < 0) return 1;
    if (bi < 0) return -1;
    return ai - bi;
  });

  return `${prefix}${result.map(([k, v]) => `${k}: ${v}`).join(", ")}${suffix}`;
}

const ADDABLE_BY_TYPE: Record<string, string[]> = {
  constant:          ["value", "start", "end", "duration"],
  linear:            ["from", "to", "rate", "start", "end", "duration"],
  smooth:            ["from", "to", "start", "end", "duration"],
  "sine-wave":     ["base", "amplitude", "min", "max", "phase", "period", "frequency", "start", "end", "duration"],
  "square-wave":   ["base", "amplitude", "min", "max", "phase", "period", "frequency", "start", "end", "duration"],
  "triangle-wave": ["base", "amplitude", "min", "max", "phase", "period", "frequency", "start", "end", "duration"],
  "sawtooth-wave": ["base", "amplitude", "min", "max", "phase", "period", "frequency", "start", "end", "duration"],
};

function getAddDefault(field: string, td: TendencyInfo): number {
  switch (field) {
    case "start":     return td.start_time;
    case "end":       return td.end_time;
    case "duration":  return td.end_time - td.start_time;
    case "from":      return td.params.to ?? 0;
    case "to":        return td.params.from ?? 0;
    case "rate": {
      const dur = td.end_time - td.start_time;
      return dur > 0 ? ((td.params.to ?? 0) - (td.params.from ?? 0)) / dur : 0;
    }
    case "value":     return 0;
    case "amplitude": return td.params.amplitude ?? 1;
    case "period":    return td.params.frequency ? 1 / td.params.frequency : 1;
    case "frequency": return td.params.period ? 1 / td.params.period : 1;
    case "base":      return td.params.min !== undefined && td.params.max !== undefined
                        ? (td.params.min + td.params.max) / 2 : 0;
    case "min":       return (td.params.base ?? 0) - (td.params.amplitude ?? 1);
    case "max":       return (td.params.base ?? 0) + (td.params.amplitude ?? 1);
    default:          return 0;
  }
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  tendencies: TendencyInfo[];
  yamlContent: string;
  name: string;
  activeTendency: number | null;
  onTendencyClick: (idx: number) => void;
  onParamChange: (lineNumber: number, changes: Array<[string, number]>) => void;
  setYamlContent: (yaml: string) => void;
  parseCurrentYaml: () => void;
}

export function WaveformBasicEditor({
  tendencies, yamlContent, name,
  activeTendency, onTendencyClick,
  onParamChange, setYamlContent, parseCurrentYaml,
}: Props) {
  // Type picker: stores which card's button was clicked + its DOMRect for fixed positioning
  const [typePickerAnchor, setTypePickerAnchor] = useState<{ idx: number; rect: DOMRect } | null>(null);
  const [addPickerAnchor, setAddPickerAnchor] = useState<DOMRect | null>(null);
  const [innerTypePickerAnchor, setInnerTypePickerAnchor] = useState<{ outerIdx: number; innerIdx: number; rect: DOMRect } | null>(null);
  const [addInnerAnchor, setAddInnerAnchor] = useState<{ outerIdx: number; rect: DOMRect } | null>(null);

  // Local draft state for number inputs so mid-type keystrokes don't get overwritten
  const [focusedKey, setFocusedKey] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  // Refs for scrolling active card into view
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  // Set to true just before inserting a new tendency so the next tendencies update selects it
  const pendingSelectLastRef = useRef(false);

  useEffect(() => {
    if (pendingSelectLastRef.current && tendencies.length > 0) {
      pendingSelectLastRef.current = false;
      onTendencyClick(tendencies.length - 1);
    }
  }, [tendencies.length, onTendencyClick]);

  // Scroll active card into view whenever activeTendency changes externally (plot click)
  useEffect(() => {
    if (activeTendency !== null) {
      cardRefs.current[activeTendency]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeTendency]);

  const getLastEndValue = useCallback((): number => {
    if (!tendencies.length) return 0;
    return getTendencyEndValue(tendencies[tendencies.length - 1]);
  }, [tendencies]);

  // ── Structural mutations ──────────────────────────────────────────────────

  const insertLine = useCallback((newLine: string) => {
    const bounds = findSectionBounds(yamlContent, name);
    if (!bounds) return;
    const lines = yamlContent.split("\n");
    // Match the indentation of existing tendency lines; fall back to key-indent + 2 spaces
    let tendencyIndent = bounds.indent + "  ";
    for (let i = bounds.startLine + 1; i < bounds.endLine; i++) {
      const raw = lines[i];
      const trimmed = raw.trimStart();
      if (trimmed.startsWith("- ")) {
        tendencyIndent = raw.slice(0, raw.length - trimmed.length);
        break;
      }
    }
    lines.splice(bounds.endLine, 0, `${tendencyIndent}${newLine}`);
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [yamlContent, name, setYamlContent, parseCurrentYaml]);

  // Insert multiple lines at the section end (each line is prefixed with tendencyIndent)
  const insertLines = useCallback((newLines: string[]) => {
    const bounds = findSectionBounds(yamlContent, name);
    if (!bounds) return;
    const lines = yamlContent.split("\n");
    let tendencyIndent = bounds.indent + "  ";
    for (let i = bounds.startLine + 1; i < bounds.endLine; i++) {
      const raw = lines[i];
      const trimmed = raw.trimStart();
      if (trimmed.startsWith("- ")) {
        tendencyIndent = raw.slice(0, raw.length - trimmed.length);
        break;
      }
    }
    lines.splice(bounds.endLine, 0, ...newLines.map(l => `${tendencyIndent}${l}`));
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [yamlContent, name, setYamlContent, parseCurrentYaml]);

  const handleAddTendency = useCallback((type: string) => {
    setAddPickerAnchor(null);
    setTypePickerAnchor(null);
    pendingSelectLastRef.current = true;
    const prevEndVal = getLastEndValue();
    const prevEndTime = tendencies.length > 0 ? tendencies[tendencies.length - 1].end_time : 0;
    if (type === "repeat") {
      insertLines([
        `- type: repeat`,
        `  duration: 10`,
        `  waveform:`,
        `    - {type: constant, value: ${fmtNum(prevEndVal)}, duration: 1}`,
      ]);
      return;
    }
    let line: string;
    if (type === "piecewise") {
      const t0 = fmtNum(prevEndTime), t1 = fmtNum(prevEndTime + 10), v = fmtNum(prevEndVal);
      line = `- {type: piecewise, time: [${t0}, ${t1}], value: [${v}, ${v}]}`;
    } else {
      line = serializeTendencyLine(type, getDefaultParams(type, prevEndVal));
    }
    insertLine(line);
  }, [getLastEndValue, tendencies, insertLine, insertLines]);

  const handleChangeTendencyType = useCallback((idx: number, newType: string) => {
    setTypePickerAnchor(null);
    const td = tendencies[idx];
    if (!td) return;
    const prevVal = td.params.to ?? td.params.value ?? td.params.base ?? 0;
    const lines = yamlContent.split("\n");
    const origLine = lines[td.line_number] ?? "";
    const lineIndent = origLine.match(/^(\s*)/)?.[1] ?? "";
    if (newType === "piecewise") {
      const t0 = fmtNum(td.start_time), t1 = fmtNum(td.end_time), v = fmtNum(prevVal);
      lines[td.line_number] = `${lineIndent}- {type: piecewise, time: [${t0}, ${t1}], value: [${v}, ${v}]}`;
    } else if (newType === "repeat") {
      const cont = lineIndent + "  ";
      const innerIndent = lineIndent + "    ";
      lines.splice(td.line_number, 1,
        `${lineIndent}- type: repeat`,
        `${cont}duration: ${fmtNum(td.end_time - td.start_time)}`,
        `${cont}waveform:`,
        `${innerIndent}- {type: constant, value: ${fmtNum(prevVal)}, duration: 1}`,
      );
    } else {
      lines[td.line_number] = `${lineIndent}${serializeTendencyLine(newType, getDefaultParams(newType, prevVal))}`;
    }
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [tendencies, yamlContent, setYamlContent, parseCurrentYaml]);

  const handleRemoveTendency = useCallback((idx: number) => {
    const td = tendencies[idx];
    if (!td) return;
    if (tendencies.length <= 1) return;
    const lines = yamlContent.split("\n");
    // Detect block range: include all lines with greater indentation than the "- " bullet
    const origLine = lines[td.line_number] ?? "";
    const leadSpaces = (origLine.match(/^(\s*)-/)?.[1] ?? "").length;
    let i = td.line_number + 1;
    while (i < lines.length) {
      const ln = lines[i];
      const trimmed = ln.trimStart();
      if (trimmed === "") { i++; continue; }
      if (ln.length - trimmed.length <= leadSpaces) break;
      i++;
    }
    lines.splice(td.line_number, i - td.line_number);
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [tendencies, yamlContent, setYamlContent, parseCurrentYaml]);

  const handleRemoveField = useCallback((td: TendencyInfo, field: string) => {
    const lines = yamlContent.split("\n");
    lines[td.line_number] = rewriteTendencyLine(lines[td.line_number], [field], []);
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [yamlContent, setYamlContent, parseCurrentYaml]);

  const handleAddParam = useCallback((td: TendencyInfo, field: string, defaultVal: number) => {
    const lines = yamlContent.split("\n");
    lines[td.line_number] = rewriteTendencyLine(lines[td.line_number], [], [[field, defaultVal]]);
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [yamlContent, setYamlContent, parseCurrentYaml]);

  // ── Inner-waveform mutations (for repeat tendencies) ──────────────────────

  const handleExpandRepeat = useCallback((outerTd: TendencyInfo) => {
    const lines = yamlContent.split("\n");
    const origLine = lines[outerTd.line_number] ?? "";
    const lineIndent = origLine.match(/^(\s*)/)?.[1] ?? "";
    const cont = lineIndent + "  ";
    const innerIndent = lineIndent + "    ";
    const newLines = [`${lineIndent}- type: repeat`];
    for (const [k, v] of Object.entries(outerTd.params)) {
      newLines.push(`${cont}${k}: ${fmtNum(v)}`);
    }
    newLines.push(`${cont}waveform:`);
    for (const it of (outerTd.inner_tendencies ?? [])) {
      newLines.push(`${innerIndent}${serializeTendencyLine(it.type, it.params)}`);
    }
    lines.splice(outerTd.line_number, 1, ...newLines);
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [yamlContent, setYamlContent, parseCurrentYaml]);

  const handleChangeInnerType = useCallback((innerTd: TendencyInfo, newType: string) => {
    setInnerTypePickerAnchor(null);
    const prevVal = innerTd.params.to ?? innerTd.params.value ?? innerTd.params.base ?? 0;
    const newLine = serializeTendencyLine(newType, getDefaultParams(newType, prevVal));
    const lines = yamlContent.split("\n");
    const lineIndent = lines[innerTd.line_number]?.match(/^(\s*)/)?.[1] ?? "";
    lines[innerTd.line_number] = `${lineIndent}${newLine}`;
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [yamlContent, setYamlContent, parseCurrentYaml]);

  const handleRemoveInnerTendency = useCallback((outerTd: TendencyInfo, innerTd: TendencyInfo) => {
    if ((outerTd.inner_tendencies ?? []).length <= 1) return;
    const lines = yamlContent.split("\n");
    lines.splice(innerTd.line_number, 1);
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [yamlContent, setYamlContent, parseCurrentYaml]);

  const handleAddInnerTendency = useCallback((outerTd: TendencyInfo, type: string) => {
    setAddInnerAnchor(null);
    const inner = outerTd.inner_tendencies ?? [];
    if (!inner.length) return;
    const lastLine = inner[inner.length - 1].line_number;
    const lines = yamlContent.split("\n");
    const indent = lines[lastLine]?.match(/^(\s*)/)?.[1] ?? "        ";
    const prevEndVal = getTendencyEndValue(inner[inner.length - 1]);
    lines.splice(lastLine + 1, 0, `${indent}${serializeTendencyLine(type, getDefaultParams(type, prevEndVal))}`);
    setYamlContent(lines.join("\n"));
    parseCurrentYaml();
  }, [yamlContent, setYamlContent, parseCurrentYaml]);

  // ── Input handlers ────────────────────────────────────────────────────────

  const handleFocus = useCallback((key: string, val: number, tendencyIdx: number) => {
    setFocusedKey(key);
    setDrafts(d => ({ ...d, [key]: fmtNum(val) }));
    onTendencyClick(tendencyIdx);
  }, [onTendencyClick]);

  const handleChange = useCallback((key: string, raw: string) => {
    setDrafts(d => ({ ...d, [key]: raw }));
    // No onParamChange here — YAML updates on blur only.
    // The drafts state gives immediate visual feedback while typing.
  }, []);

  const handleBlur = useCallback((key: string, raw: string, lineNum: number, field: string) => {
    const v = parseFloat(raw);
    if (isFinite(v)) onParamChange(lineNum, [[field, v]]);
    setFocusedKey(null);
  }, [onParamChange]);

  const displayVal = (key: string, val: number) =>
    focusedKey === key ? (drafts[key] ?? fmtNum(val)) : fmtNum(val);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="wbe-root">
      <div className="wbe-cards">
        {tendencies.length === 0 && (
          <div className="wbe-empty">
            <span>No tendencies yet</span>
            <span className="wbe-empty-hint">Click "Add tendency" below to get started</span>
          </div>
        )}

        {tendencies.map((td, idx) => {
          const color = COLORS[idx % COLORS.length];
          const isComplex = COMPLEX_TYPES.has(td.type);
          const catalog = TENDENCY_CATALOG.find(c => c.type === td.type);

          // Fields actually present in YAML params, in canonical order
          const displayFields = [
            ...FIELD_ORDER.filter(f => f in td.params),
            ...Object.keys(td.params).filter(k => !FIELD_ORDER.includes(k)),
          ];

          // Fields that can be added (not yet present in params)
          const addable = td.type === "piecewise" ? []
            : td.type === "repeat" ? ["duration", "frequency", "period"].filter(f => !(f in td.params))
            : (ADDABLE_BY_TYPE[td.type] ?? []).filter(f => !(f in td.params));

          return (
            <div
              key={td.line_number}
              ref={el => { cardRefs.current[idx] = el; }}
              className={`wbe-card${td.type === "piecewise" ? " wbe-card-complex" : ""}${activeTendency === idx ? " active" : ""}`}
              style={{ "--card-color": color } as React.CSSProperties}
            >
              {/* Card header */}
              <div className="wbe-card-head" onClick={() => onTendencyClick(idx)} style={{ cursor: "pointer" }}>
                <span className="wbe-card-dot" style={{ background: color }} />

                {isComplex ? (
                  <span className="wbe-type-badge">{catalog?.icon} {td.type}</span>
                ) : (
                  <div className="wbe-type-wrap">
                    <button
                      className="wbe-type-btn"
                      onClick={e => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        setTypePickerAnchor(prev => prev?.idx === idx ? null : { idx, rect });
                      }}
                      title="Change type"
                    >
                      <span className="wbe-type-icon">{catalog?.icon ?? "•"}</span>
                      <span className="wbe-type-name">{catalog?.label ?? td.type}</span>
                      <span className="wbe-type-chevron">▾</span>
                    </button>
                    {typePickerAnchor?.idx === idx && (
                      <InlinePicker
                        onSelect={t => { handleChangeTendencyType(idx, t); setTypePickerAnchor(null); }}
                        onClose={() => setTypePickerAnchor(null)}
                        anchorRect={typePickerAnchor.rect}
                      />
                    )}
                  </div>
                )}

                <span className="wbe-time-range">
                  {fmtNum(td.start_time)}–{fmtNum(td.end_time)} s
                </span>

                <button
                  className="wbe-remove-btn"
                  onClick={() => handleRemoveTendency(idx)}
                  disabled={tendencies.length <= 1}
                  title={tendencies.length <= 1 ? "Can't remove the only tendency" : "Remove"}
                >
                  ×
                </button>
              </div>

              {/* Card body */}
              {td.type === "piecewise" ? (
                <div className="wbe-complex-notice">
                  <span className="wbe-complex-icon">◆</span>
                  Piecewise — drag handles in the plot to edit; click path to add a point
                </div>
              ) : (
                <>
                  {displayFields.length > 0 && (
                    <div className="wbe-params-grid">
                      {displayFields.map(field => {
                        const val = td.params[field] ?? 0;
                        const key = `${idx}:${field}`;
                        return (
                          <label key={field} className="wbe-param">
                            <span className="wbe-param-label">
                              {FIELD_LABELS[field] ?? field}
                              {FIELD_UNITS[field] && (
                                <span className="wbe-param-unit">{FIELD_UNITS[field]}</span>
                              )}
                              <button
                                className="wbe-field-rm"
                                tabIndex={-1}
                                onClick={e => { e.preventDefault(); e.stopPropagation(); handleRemoveField(td, field); }}
                                title={`Remove ${field}`}
                              >×</button>
                            </span>
                            <input
                              className="wbe-param-input"
                              type="number"
                              step="any"
                              value={displayVal(key, val)}
                              onFocus={() => handleFocus(key, val, idx)}
                              onChange={e => handleChange(key, e.target.value)}
                              onBlur={e => handleBlur(key, e.target.value, td.line_number, field)}
                              onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                            />
                          </label>
                        );
                      })}
                    </div>
                  )}

                  {addable.length > 0 && (
                    <div className="wbe-addable-row">
                      {addable.map(f => (
                        <button
                          key={f}
                          className="wbe-addable-btn"
                          onClick={() => handleAddParam(td, f, getAddDefault(f, td))}
                        >
                          + {FIELD_LABELS[f] ?? f}
                        </button>
                      ))}
                    </div>
                  )}

                  {td.type === "repeat" && (() => {
                    const inner = td.inner_tendencies ?? [];
                    const isInline = inner.length > 0 && inner[0].line_number === td.line_number;
                    return (
                      <div className="wbe-inner-section">
                        <div className="wbe-inner-header">⟲ Inner waveform</div>
                        {isInline ? (
                          <div className="wbe-inner-expand">
                            <button className="wbe-expand-btn" onClick={() => handleExpandRepeat(td)}>
                              Expand to block format to edit
                            </button>
                          </div>
                        ) : (
                          <>
                            {inner.map((innerTd, innerIdx) => {
                              const innerCatalog = TENDENCY_CATALOG.find(c => c.type === innerTd.type);
                              const innerIsComplex = COMPLEX_TYPES.has(innerTd.type);
                              const innerDisplayFields = [
                                ...FIELD_ORDER.filter(f => f in innerTd.params),
                                ...Object.keys(innerTd.params).filter(k => !FIELD_ORDER.includes(k)),
                              ];
                              const innerAddable = innerIsComplex ? []
                                : (ADDABLE_BY_TYPE[innerTd.type] ?? []).filter(f => !(f in innerTd.params));
                              return (
                                <div key={`${innerTd.line_number}-${innerIdx}`} className="wbe-inner-card">
                                  <div className="wbe-inner-card-head">
                                    {innerIsComplex ? (
                                      <span className="wbe-type-badge">{innerCatalog?.icon} {innerTd.type}</span>
                                    ) : (
                                      <div className="wbe-type-wrap">
                                        <button
                                          className="wbe-type-btn"
                                          onClick={e => {
                                            e.stopPropagation();
                                            const rect = e.currentTarget.getBoundingClientRect();
                                            setInnerTypePickerAnchor(prev =>
                                              prev?.outerIdx === idx && prev.innerIdx === innerIdx
                                                ? null : { outerIdx: idx, innerIdx, rect }
                                            );
                                          }}
                                        >
                                          <span className="wbe-type-icon">{innerCatalog?.icon ?? "•"}</span>
                                          <span className="wbe-type-name">{innerCatalog?.label ?? innerTd.type}</span>
                                          <span className="wbe-type-chevron">▾</span>
                                        </button>
                                        {innerTypePickerAnchor?.outerIdx === idx && innerTypePickerAnchor.innerIdx === innerIdx && (
                                          <InlinePicker
                                            onSelect={t => handleChangeInnerType(innerTd, t)}
                                            onClose={() => setInnerTypePickerAnchor(null)}
                                            excludeComplex
                                            anchorRect={innerTypePickerAnchor.rect}
                                          />
                                        )}
                                      </div>
                                    )}
                                    <span className="wbe-time-range">
                                      {fmtNum(innerTd.start_time)}–{fmtNum(innerTd.end_time)} s
                                    </span>
                                    <button
                                      className="wbe-remove-btn"
                                      onClick={e => { e.stopPropagation(); handleRemoveInnerTendency(td, innerTd); }}
                                      disabled={inner.length <= 1}
                                      title={inner.length <= 1 ? "Can't remove the only inner tendency" : "Remove"}
                                    >×</button>
                                  </div>
                                  {innerIsComplex ? (
                                    <div className="wbe-complex-notice wbe-complex-notice--sm">
                                      <span className="wbe-complex-icon">⚙</span>
                                      Use Advanced mode to edit
                                    </div>
                                  ) : (
                                    <>
                                      {innerDisplayFields.length > 0 && (
                                        <div className="wbe-params-grid">
                                          {innerDisplayFields.map(field => {
                                            const val = innerTd.params[field] ?? 0;
                                            const key = `inner:${idx}:${innerIdx}:${field}`;
                                            return (
                                              <label key={field} className="wbe-param">
                                                <span className="wbe-param-label">
                                                  {FIELD_LABELS[field] ?? field}
                                                  {FIELD_UNITS[field] && (
                                                    <span className="wbe-param-unit">{FIELD_UNITS[field]}</span>
                                                  )}
                                                  <button
                                                    className="wbe-field-rm"
                                                    tabIndex={-1}
                                                    onClick={e => { e.preventDefault(); e.stopPropagation(); handleRemoveField(innerTd, field); }}
                                                    title={`Remove ${field}`}
                                                  >×</button>
                                                </span>
                                                <input
                                                  className="wbe-param-input"
                                                  type="number"
                                                  step="any"
                                                  value={displayVal(key, val)}
                                                  onFocus={() => handleFocus(key, val, idx)}
                                                  onChange={e => handleChange(key, e.target.value)}
                                                  onBlur={e => handleBlur(key, e.target.value, innerTd.line_number, field)}
                                                  onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                                                />
                                              </label>
                                            );
                                          })}
                                        </div>
                                      )}
                                      {innerAddable.length > 0 && (
                                        <div className="wbe-addable-row">
                                          {innerAddable.map(f => (
                                            <button
                                              key={f}
                                              className="wbe-addable-btn"
                                              onClick={() => handleAddParam(innerTd, f, getAddDefault(f, innerTd))}
                                            >
                                              + {FIELD_LABELS[f] ?? f}
                                            </button>
                                          ))}
                                        </div>
                                      )}
                                    </>
                                  )}
                                </div>
                              );
                            })}
                            <button
                              className={`wbe-add-inner-btn${addInnerAnchor?.outerIdx === idx ? " open" : ""}`}
                              onClick={e => {
                                e.stopPropagation();
                                const rect = e.currentTarget.getBoundingClientRect();
                                setAddInnerAnchor(prev => prev?.outerIdx === idx ? null : { outerIdx: idx, rect });
                                setTypePickerAnchor(null);
                                setInnerTypePickerAnchor(null);
                              }}
                            >
                              <span>+</span> Add inner tendency
                            </button>
                            {addInnerAnchor?.outerIdx === idx && (
                              <InlinePicker
                                onSelect={t => handleAddInnerTendency(td, t)}
                                onClose={() => setAddInnerAnchor(null)}
                                excludeComplex
                                anchorRect={addInnerAnchor.rect}
                              />
                            )}
                          </>
                        )}
                      </div>
                    );
                  })()}
                </>
              )}
            </div>
          );
        })}

        {/* Add tendency button — lives inline after the last card */}
        <button
          className={`wbe-add-btn${addPickerAnchor ? " open" : ""}`}
          onClick={e => {
            const rect = e.currentTarget.getBoundingClientRect();
            setAddPickerAnchor(prev => prev ? null : rect);
            setTypePickerAnchor(null);
          }}
        >
          <span>+</span> Add tendency
        </button>
        {addPickerAnchor && (
          <InlinePicker
            onSelect={handleAddTendency}
            onClose={() => setAddPickerAnchor(null)}
            anchorRect={addPickerAnchor}
          />
        )}
      </div>
    </div>
  );
}

// ── Type picker ───────────────────────────────────────────────────────────────

interface PickerProps {
  onSelect: (type: string) => void;
  onClose: () => void;
  excludeComplex?: boolean;
  position?: "down" | "up";
  anchorRect?: DOMRect; // if set, use position:fixed at the button's viewport coordinates
}

function InlinePicker({ onSelect, onClose, excludeComplex, position = "down", anchorRect }: PickerProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    // defer so the click that opened the picker doesn't immediately close it
    const t = setTimeout(() => document.addEventListener("mousedown", handler), 0);
    return () => { clearTimeout(t); document.removeEventListener("mousedown", handler); };
  }, [onClose]);

  const groups = ["Basic", "Periodic", "Complex"] as const;
  const items = TENDENCY_CATALOG.filter(c => !(excludeComplex && COMPLEX_TYPES.has(c.type)));

  // Fixed positioning escapes overflow:hidden/auto scroll containers
  const fixedStyle: React.CSSProperties | undefined = anchorRect ? {
    position: "fixed",
    top: anchorRect.bottom + 4,
    left: anchorRect.left,
    right: "auto",
    minWidth: 200,
    zIndex: 1000,
  } : undefined;

  return (
    <div
      className={`wbe-picker${anchorRect ? "" : ` wbe-picker-${position}`}`}
      ref={ref}
      style={fixedStyle}
    >
      {groups.map(g => {
        const groupItems = items.filter(c => c.group === g);
        if (!groupItems.length) return null;
        return (
          <div key={g} className="wbe-picker-group">
            <div className="wbe-picker-group-label">{g}</div>
            {groupItems.map(c => (
              <button
                key={c.type}
                className="wbe-picker-item"
                onClick={() => onSelect(c.type)}
              >
                <span className="wbe-picker-icon">{c.icon}</span>
                <span className="wbe-picker-name">{c.label}</span>
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}
