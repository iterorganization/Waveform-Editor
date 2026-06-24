import { useRef } from "react";
import { useStore } from "../store";

export function Header() {
  const {
    yamlContent, setYamlContent, parseCurrentYaml,
    niceRunning, runNice, stopNice,
    niceProgress, niceStatus,
    setShowSettings, showAdvancedEditor, setShowAdvancedEditor,
  } = useStore();

  const fileInputRef = useRef<HTMLInputElement>(null);

  const openFile = () => fileInputRef.current?.click();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setYamlContent(text);
      parseCurrentYaml();
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const saveFile = () => {
    const blob = new Blob([yamlContent], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "waveforms.yaml";
    a.click();
    URL.revokeObjectURL(url);
  };

  const progressPct = niceProgress.total
    ? Math.round((niceProgress.current / niceProgress.total) * 100)
    : 0;

  return (
    <header className="header">
      <span className="header-brand">Waveform Editor</span>
      <div className="header-sep" />

      <button className="btn btn-sm" onClick={openFile} title="Open YAML file">
        📂 Open
      </button>
      <button className="btn btn-sm" onClick={saveFile} title="Save YAML file">
        💾 Save
      </button>
      <button
        className="btn btn-sm"
        onClick={() => setShowAdvancedEditor(!showAdvancedEditor)}
        title="Toggle raw YAML editor"
        style={{ borderColor: showAdvancedEditor ? "var(--accent)" : undefined }}
      >
        {showAdvancedEditor ? "📝 YAML" : "🔧 Advanced"}
      </button>

      <div className="header-sep" />

      {niceRunning ? (
        <>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
            {niceStatus} ({progressPct}%)
          </span>
          <button className="btn btn-sm btn-danger" onClick={stopNice}>
            ⏹ Stop
          </button>
        </>
      ) : (
        <button className="btn btn-sm btn-success" onClick={runNice} title="Run NICE across timeline">
          ▶ Run NICE
        </button>
      )}

      {!niceRunning && niceStatus && (
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{niceStatus}</span>
      )}

      <div className="header-spacer" />

      <button className="btn btn-sm" onClick={() => setShowSettings(true)} title="Settings">
        ⚙ Settings
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept=".yaml,.yml"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
    </header>
  );
}
