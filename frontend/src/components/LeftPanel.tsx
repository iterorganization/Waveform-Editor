import { lazy, Suspense, useRef, useState } from "react";
import { useStore } from "../store";
import { WaveformTimeline } from "./timeline/WaveformTimeline";

const MonacoEditor = lazy(() => import("@monaco-editor/react"));

export function LeftPanel() {
  const { showAdvancedEditor, yamlContent, setYamlContent, parseCurrentYaml, yamlError } =
    useStore();

  const [collapsed, setCollapsed] = useState(false);
  const parseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setYamlContent(value);
      if (parseTimerRef.current) clearTimeout(parseTimerRef.current);
      parseTimerRef.current = setTimeout(parseCurrentYaml, 400);
    }
  };

  if (collapsed) {
    return (
      <div className="left-panel" data-collapsed="true">
        <button
          className="left-panel-toggle"
          onClick={() => setCollapsed(false)}
          title="Expand panel"
        >
          ›
        </button>
      </div>
    );
  }

  return (
    <div className="left-panel">
      <div className="left-panel-toolbar">
        {showAdvancedEditor && <span className="label">YAML Editor (Advanced)</span>}
        {yamlError && (
          <span style={{ fontSize: 11, color: "var(--red)" }} title={yamlError}>
            ⚠ {showAdvancedEditor ? "Parse error" : "Error"}
          </span>
        )}
        <button
          className="left-panel-toggle"
          style={{ marginLeft: "auto" }}
          onClick={() => setCollapsed(true)}
          title="Collapse panel"
        >
          ‹
        </button>
      </div>
      {showAdvancedEditor ? (
        <Suspense fallback={<div style={{ padding: 12 }}>Loading editor…</div>}>
          <MonacoEditor
            height="100%"
            language="yaml"
            theme="vs-dark"
            value={yamlContent}
            onChange={handleEditorChange}
            options={{
              minimap: { enabled: false },
              fontSize: 12,
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              wordWrap: "on",
            }}
          />
        </Suspense>
      ) : (
        <WaveformTimeline />
      )}
    </div>
  );
}
