import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { api } from "../../api";
import { adaptivePoints, useStore } from "../../store";
import type { TendencyInfo } from "../../types";
import { WaveformPlot } from "./WaveformPlot";
import { WaveformBasicEditor } from "./WaveformBasicEditor";

const MonacoEditor = lazy(() => import("@monaco-editor/react"));

// Mapping from YAML param key to NICE IDS unit labels
const UNITS: Record<string, string> = {
  kappa: "—", delta: "—", a: "m", center_r: "m", center_z: "m",
  rx: "m", zx: "m", ip: "A", b0: "T", r0: "m",
  profile_alpha: "—", profile_beta: "—", profile_gamma: "—",
};

interface WaveformViewerProps {
  /** Pin a specific waveform name instead of using the store's viewerWaveformName */
  forceName?: string;
  /** Override the close action (default: store's closeWaveformViewer) */
  onClose?: () => void;
  /** Render as an inline panel column instead of a fixed full-screen overlay */
  inline?: boolean;
  /** Extra inline styles applied to the root element (e.g. to override flex sizing) */
  style?: React.CSSProperties;
}

export function WaveformViewer({ forceName, onClose, inline = false, style: styleProp }: WaveformViewerProps = {}) {
  const { viewerWaveformName, closeWaveformViewer, yamlContent, debouncedYamlContent, setYamlContent, parseCurrentYaml, parsedConfig, yamlError, yamlAnnotations, undo, redo, yamlHistory, yamlHistoryIndex, shapePreviewData, shapePreviewIndex, tendenciesCache, tendencyErrors, addTendencyWatch, removeTendencyWatch } =
    useStore();
  const scrubTime = shapePreviewData?.times[shapePreviewIndex] ?? null;

  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [activeTendency, setActiveTendency] = useState<number | null>(null);
  const [waveformData, setWaveformData] = useState<{ times: number[]; values: number[] }>({ times: [], values: [] });
  const [evalError, setEvalError] = useState("");
  const [basicMode, setBasicMode] = useState(true);

  const [sectionStartLine, setSectionStartLine] = useState(0);

  // When Monaco is the source of a YAML change, skip pushing back to the editor
  const fromFilteredEditorRef = useRef(false);

  const parseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Stable ref so handleParamChange doesn't re-create on every YAML keystroke
  const yamlContentRef = useRef(yamlContent);
  useEffect(() => { yamlContentRef.current = yamlContent; }, [yamlContent]);

  // Resizable editor pane
  const [editorWidth, setEditorWidth] = useState(420);
  const [isResizing, setIsResizing] = useState(false);
  const resizeStartX = useRef(0);
  const resizeStartWidth = useRef(0);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    resizeStartX.current = e.clientX;
    resizeStartWidth.current = editorWidth;
    setIsResizing(true);
  }, [editorWidth]);

  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: MouseEvent) => {
      const delta = e.clientX - resizeStartX.current;
      setEditorWidth(Math.max(160, resizeStartWidth.current + delta));
    };
    const onUp = () => setIsResizing(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isResizing]);

  const name = forceName ?? viewerWaveformName ?? "";
  const handleClose = onClose ?? closeWaveformViewer;
  const units = UNITS[name] ?? "a.u.";

  // Keep the filtered editor in sync with external yamlContent changes (drag, etc.)
  // Skip setValue when Monaco is hidden (basic mode) — Monaco's YAML tokenizer is
  // expensive and runs even on hidden editors. Push content when switching to advanced.
  useEffect(() => {
    if (!name || !yamlContent) return;
    const section = extractWaveformSection(yamlContent, name);
    if (!section) return;
    setSectionStartLine(section.startLine);
    if (fromFilteredEditorRef.current) {
      // We caused this change — editor already shows it, only update line offset
      fromFilteredEditorRef.current = false;
      return;
    }
    if (!basicMode) {
      editorRef.current?.setValue(section.filteredContent);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, yamlContent, basicMode]);

  // Tendency metadata comes from the store cache: registering the name here
  // makes every parse round trip include it (no per-viewer API calls).
  useEffect(() => {
    if (!name) return;
    addTendencyWatch([name]);
    return () => removeTendencyWatch([name]);
  }, [name, addTendencyWatch, removeTendencyWatch]);
  const tendencies = useMemo(
    () => (name ? tendenciesCache[name] ?? [] : []),
    [name, tendenciesCache],
  );
  const tendencyError = name ? tendencyErrors[name] ?? "" : "";

  // Waveform data for the plot: reuse the shared preview evaluation (already
  // fetched in the parse round trip). Fall back to a direct evaluate call only
  // when the waveform is missing from the preview (e.g. it failed to evaluate).
  useEffect(() => {
    if (!name) return;
    if (shapePreviewData?.waveforms[name]) {
      setEvalError("");
      setWaveformData({ times: shapePreviewData.times, values: shapePreviewData.waveforms[name] });
      return;
    }
    if (!parsedConfig || !debouncedYamlContent) return;
    const tStart = parsedConfig.time_start;
    const tEnd = parsedConfig.time_end;
    if (tEnd <= tStart) return;
    const n = adaptivePoints(debouncedYamlContent, tEnd - tStart, 600, 5000);
    const times = Array.from({ length: n }, (_, i) => tStart + (i / (n - 1)) * (tEnd - tStart));
    api.evaluateWaveforms(debouncedYamlContent, times, [name])
      .then((r) => {
        if (r.error) { setEvalError(r.error); return; }
        setEvalError("");
        const wf = r.waveforms.find((w) => w.name === name);
        if (wf) setWaveformData({ times: wf.times, values: wf.values });
      })
      .catch(() => {});
  }, [name, parsedConfig, debouncedYamlContent, shapePreviewData]);

  // Editor mount: set initial content and register cursor handler
  const handleEditorMount = useCallback((ed: editor.IStandaloneCodeEditor) => {
    editorRef.current = ed;
    const section = extractWaveformSection(yamlContent, name);
    if (section) {
      ed.setValue(section.filteredContent);
      setSectionStartLine(section.startLine);
    }
  }, [yamlContent, name]); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-register cursor listener when tendencies or section offset changes
  useEffect(() => {
    const ed = editorRef.current;
    if (!ed) return;
    const disp = ed.onDidChangeCursorPosition((e) => {
      const lineIdx = e.position.lineNumber - 1 + sectionStartLine;
      setActiveTendency(findTendencyAtLine(lineIdx, tendencies));
    });
    return () => disp.dispose();
  }, [tendencies, sectionStartLine]);

  // Tendency click in plot → jump cursor in editor (advanced mode only)
  const handleTendencyClick = useCallback((idx: number) => {
    setActiveTendency(idx);
    // Monaco is hidden in basic mode — never call its methods when it's not visible.
    // Even with display:none, revealLineInCenter/setPosition/focus can trigger
    // internal Monaco layout loops that freeze the browser.
    if (basicMode || !editorRef.current) return;
    const td = tendencies[idx];
    if (!td) return;
    const line = td.line_number - sectionStartLine + 1;
    if (line >= 1) {
      editorRef.current.revealLineInCenter(line);
      editorRef.current.setPosition({ lineNumber: line, column: 1 });
      editorRef.current.focus();
    }
  }, [tendencies, sectionStartLine, basicMode]);

  // Monaco onChange: sync filtered edit back into the full YAML (no controlled re-push)
  const handleFilteredChange = useCallback((v: string | undefined) => {
    if (v === undefined) return;
    const newFull = syncFilteredToFull(v, yamlContent, name);
    if (newFull !== yamlContent) {
      fromFilteredEditorRef.current = true;
      setYamlContent(newFull);
      // Debounce the parse call — avoids a backend request on every keystroke
      if (parseTimerRef.current) clearTimeout(parseTimerRef.current);
      parseTimerRef.current = setTimeout(parseCurrentYaml, 400);
    }
  }, [yamlContent, name, setYamlContent, parseCurrentYaml]);

  // YAML param change from drag handles or basic editor blur.
  // Reads yamlContent via ref so this callback is stable — doesn't recreate on
  // every YAML change, preventing unnecessary re-renders of WaveformPlot/BasicEditor.
  const handleParamChange = useCallback((lineNumber: number, changes: Array<[string, number]>) => {
    const lines = yamlContentRef.current.split("\n");
    if (lineNumber >= lines.length) return;
    let line = lines[lineNumber];
    let anyChanged = false;

    for (const [key, value] of changes) {
      let formatted: string;
      const abs = Math.abs(value);
      if (abs >= 1e6 || (abs < 1e-3 && abs > 0)) {
        formatted = value.toPrecision(5);
      } else if (abs >= 100) {
        formatted = value.toFixed(2);
      } else {
        formatted = value.toFixed(4).replace(/\.?0+$/, "");
      }
      const updated = line.replace(
        new RegExp(`(\\b${key}:\\s*)([^,}\\s]+)`),
        `$1${formatted}`,
      );
      if (updated !== line) { line = updated; anyChanged = true; }
    }

    if (!anyChanged) return;
    lines[lineNumber] = line;
    setYamlContent(lines.join("\n"));
    if (parseTimerRef.current) clearTimeout(parseTimerRef.current);
    parseTimerRef.current = setTimeout(parseCurrentYaml, 400);
  }, [setYamlContent, parseCurrentYaml]); // stable — no yamlContent dep

  // Piecewise point array change from drag/click-to-add in WaveformPlot.
  const handlePiecewiseChange = useCallback((lineNumber: number, times: number[], values: number[]) => {
    const lines = yamlContentRef.current.split("\n");
    if (lineNumber >= lines.length) return;
    const line = lines[lineNumber];
    const m = line.match(/^(\s*-\s*\{)(.+?)(\}\s*)$/);
    if (!m) return;
    const [, prefix, , suffix] = m;
    const fmt = (v: number) => {
      const abs = Math.abs(v);
      if (abs === 0) return "0";
      if (abs >= 1e5 || (abs < 1e-3 && abs > 0)) return parseFloat(v.toPrecision(5)).toString();
      return parseFloat(v.toPrecision(6)).toString();
    };
    const tStr = times.map(fmt).join(", ");
    const vStr = values.map(fmt).join(", ");
    lines[lineNumber] = `${prefix}type: piecewise, time: [${tStr}], value: [${vStr}]${suffix}`;
    setYamlContent(lines.join("\n"));
    if (parseTimerRef.current) clearTimeout(parseTimerRef.current);
    parseTimerRef.current = setTimeout(parseCurrentYaml, 400);
  }, [setYamlContent, parseCurrentYaml]);

  // Keyboard: Escape closes; Ctrl+Z/Y undo/redo (skip when Monaco has focus)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { handleClose(); return; }
      if (e.ctrlKey || e.metaKey) {
        const inMonaco = !!(e.target as Element)?.closest?.(".monaco-editor");
        if (!inMonaco) {
          if (e.key === "z" && !e.shiftKey) { e.preventDefault(); undo(); return; }
          if (e.key === "y" || (e.key === "z" && e.shiftKey)) { e.preventDefault(); redo(); return; }
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleClose, undo, redo]);

  if (!name) return null;

  return (
    <div className={inline ? "wv-inline" : "wv-overlay"} style={{ userSelect: isResizing ? "none" : undefined, ...styleProp }}>
      {/* Header */}
      <div className="wv-header">
        <div className="wv-title">
          <span className="wv-name">{name}</span>
          {units !== "—" && units !== "a.u." && (
            <span className="wv-units">{units}</span>
          )}
          {tendencies.length > 0 && (
            <span className="wv-badge">{tendencies.length} {tendencies.length === 1 ? "tendency" : "tendencies"}</span>
          )}
        </div>
        <div className="wv-legend">
          {tendencies.map((td, i) => (
            <button
              key={i}
              className={`wv-legend-item ${activeTendency === i ? "active" : ""}`}
              style={{ "--legend-color": COLORS[i % COLORS.length] } as React.CSSProperties}
              onClick={() => handleTendencyClick(i)}
            >
              <span className="wv-legend-dot" />
              <span>{td.type}</span>
            </button>
          ))}
        </div>
        <button className="wv-close btn btn-sm" onClick={handleClose} title="Close (Esc)">
          ✕
        </button>
      </div>

      {/* Body */}
      <div className="wv-body">
        {/* Left: editor pane — basic (visual) or advanced (YAML) mode */}
        <div className="wv-editor-pane" style={{ width: editorWidth }}>
          <div className="wv-pane-label">
            <span>{name}</span>
            <div className="wv-pane-actions">
              <button
                className="wv-hist-btn"
                onClick={undo}
                disabled={yamlHistoryIndex <= 0 && yamlContent === yamlHistory[yamlHistoryIndex]}
                title="Undo (Ctrl+Z)"
              >↺</button>
              <button
                className="wv-hist-btn"
                onClick={redo}
                disabled={yamlHistoryIndex >= yamlHistory.length - 1}
                title="Redo (Ctrl+Y)"
              >↻</button>
              <button
                className={`wv-mode-toggle${!basicMode ? " active" : ""}`}
                onClick={() => setBasicMode(v => !v)}
                title={basicMode ? "Switch to YAML editor" : "Switch to visual editor"}
              >
                {basicMode ? "Advanced ›" : "‹ Basic"}
              </button>
            </div>
          </div>

          {/* Basic editor — always mounted so state isn't lost on toggle */}
          <div style={{ display: basicMode ? "flex" : "none", flex: 1, minHeight: 0, flexDirection: "column" }}>
            <WaveformBasicEditor
              tendencies={tendencies}
              yamlContent={yamlContent}
              name={name}
              activeTendency={activeTendency}
              onTendencyClick={handleTendencyClick}
              onParamChange={handleParamChange}
              setYamlContent={setYamlContent}
              parseCurrentYaml={parseCurrentYaml}
            />
          </div>

          {/* Advanced editor — lazy-loaded Monaco; hidden when in basic mode */}
          <div style={{ display: basicMode ? "none" : "flex", flex: 1, minHeight: 0, flexDirection: "column" }}>
            <Suspense fallback={<div style={{ padding: 12, color: "var(--text-muted)" }}>Loading editor…</div>}>
              <MonacoEditor
                height="100%"
                language="yaml"
                theme="vs-dark"
                defaultValue=""
                onChange={handleFilteredChange}
                onMount={handleEditorMount}
                options={{
                  minimap: { enabled: false },
                  fontSize: 12,
                  lineNumbers: (n) => String(n + sectionStartLine),
                  scrollBeyondLastLine: false,
                  wordWrap: "on",
                  renderLineHighlight: "all",
                  occurrencesHighlight: "off",
                }}
              />
            </Suspense>
          </div>
        </div>

        {/* Resize handle */}
        <div
          className={`wv-resize-handle${isResizing ? " dragging" : ""}`}
          onMouseDown={onResizeStart}
        />

        {/* Right: interactive plot */}
        <div className="wv-plot-pane">
          <div className="wv-pane-label">Interactive Plot</div>
          <div className="wv-plot-area">
            <WaveformPlot
              tendencies={tendencies}
              data={waveformData}
              activeTendency={activeTendency}
              onTendencyClick={handleTendencyClick}
              onParamChange={handleParamChange}
              onPiecewiseChange={handlePiecewiseChange}
              units={units}
              currentTime={scrubTime}
            />
          </div>
          {tendencies.length > 0 && (
            <div className="wv-hint">
              Click tendency to select · Drag ● handles to edit · Scroll to zoom · Drag to pan · Double-click to reset
            </div>
          )}
        </div>
      </div>

      {/* Error banner — fatal parse / evaluation errors */}
      {(yamlError || tendencyError || evalError) && (
        <div className="wv-error-banner">
          <span className="wv-error-icon">⚠</span>
          <span className="wv-error-text">{tendencyError || evalError || yamlError}</span>
        </div>
      )}
      {/* Warning banner — waveform-level annotations (unknown params, conflicting values, etc.) */}
      {!yamlError && !tendencyError && !evalError && yamlAnnotations.length > 0 && (
        <div className="wv-warning-banner">
          <span className="wv-error-icon">⚠</span>
          <span className="wv-error-text">
            There was an error in the YAML configuration{"\n\n"}
            {yamlAnnotations.join("\n")}
          </span>
        </div>
      )}
    </div>
  );
}

// Colours mirror WaveformPlot so legend matches
const COLORS = [
  "#4f8ef7", "#7c5cfc", "#2dd4bf", "#f97316",
  "#3ddc84", "#f59e0b", "#f472b6", "#e879f9",
];

function findTendencyAtLine(lineIdx: number, tendencies: TendencyInfo[]): number | null {
  for (let i = 0; i < tendencies.length; i++) {
    const td = tendencies[i];
    const nextLine = i < tendencies.length - 1 ? tendencies[i + 1].line_number : Infinity;
    if (lineIdx >= td.line_number && lineIdx < nextLine) return i;
  }
  return null;
}

// Extract the named waveform's YAML block, stripping common indentation.
function extractWaveformSection(yaml: string, name: string): {
  filteredContent: string;
  startLine: number;
  endLine: number;
  indent: string;
} | null {
  const lines = yaml.split("\n");
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const keyRegex = new RegExp(`^(\\s+)(${escapedName}):\\s*$`);

  let startLine = -1;
  let indent = "";

  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(keyRegex);
    if (m) { startLine = i; indent = m[1]; break; }
  }

  if (startLine === -1) return null;

  const indentLen = indent.length;
  let endLine = startLine + 1;

  while (endLine < lines.length) {
    const raw = lines[endLine];
    const trimmed = raw.trimStart();
    if (trimmed === "") { endLine++; continue; }
    const lineIndent = raw.length - trimmed.length;
    if (lineIndent <= indentLen && /^\S+:/.test(trimmed)) break;
    endLine++;
  }

  const filteredContent = lines
    .slice(startLine, endLine)
    .map((l) => (l.startsWith(indent) ? l.slice(indentLen) : l))
    .join("\n");

  return { filteredContent, startLine, endLine, indent };
}

// Splice edited filtered content back into the full YAML.
function syncFilteredToFull(filtered: string, full: string, name: string): string {
  const section = extractWaveformSection(full, name);
  if (!section) return full;
  const { startLine, endLine, indent } = section;
  const lines = full.split("\n");
  const newSection = filtered.split("\n").map((l) => (l.trim() === "" ? "" : indent + l));
  return [...lines.slice(0, startLine), ...newSection, ...lines.slice(endLine)].join("\n");
}
