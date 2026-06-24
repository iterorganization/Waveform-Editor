import { lazy, Suspense } from "react";
import { useStore } from "../store";
import { WaveformTimeline } from "./timeline/WaveformTimeline";

const MonacoEditor = lazy(() => import("@monaco-editor/react"));

export function LeftPanel() {
  const { showAdvancedEditor, yamlContent, setYamlContent, parseCurrentYaml, yamlError } =
    useStore();

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setYamlContent(value);
      parseCurrentYaml();
    }
  };

  return (
    <div className="left-panel">
      {showAdvancedEditor ? (
        <>
          <div className="left-panel-toolbar">
            <span className="label">YAML Editor (Advanced)</span>
            {yamlError && (
              <span style={{ fontSize: 11, color: "var(--red)" }} title={yamlError}>
                ⚠ Parse error
              </span>
            )}
          </div>
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
        </>
      ) : (
        <WaveformTimeline />
      )}
    </div>
  );
}
