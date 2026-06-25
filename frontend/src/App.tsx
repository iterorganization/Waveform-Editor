import { useCallback, useEffect, useRef, useState } from "react";
import { Header } from "./components/Header";
import { LeftPanel } from "./components/LeftPanel";
import { RightPanel } from "./components/RightPanel";
import { SettingsModal } from "./components/settings/SettingsModal";
import { PlaybackScrubber } from "./components/visualization/PlaybackScrubber";
import { WaveformViewer } from "./components/waveform-viewer/WaveformViewer";
import { useStore } from "./store";

function NiceStatusBar() {
  const { niceRunning, niceProgress, niceStatus, results } = useStore();
  const progressPct = niceProgress.total
    ? Math.round((niceProgress.current / niceProgress.total) * 100)
    : 0;
  return (
    <div className="status-bar">
      <div className={`status-dot ${niceRunning ? "running" : "idle"}`} />
      <span>{niceStatus || (results.length ? `${results.length} timesteps computed` : "Ready")}</span>
      {niceRunning && niceProgress.total > 0 && (
        <>
          <div className="progress-bar-outer">
            <div className="progress-bar-inner" style={{ width: `${progressPct}%` }} />
          </div>
          <span>{progressPct}%</span>
        </>
      )}
    </div>
  );
}

export default function App() {
  const { loadSettingsFromServer, parseCurrentYaml, loadMachineGeometries } = useStore();

  useEffect(() => {
    loadSettingsFromServer().then(() => {
      parseCurrentYaml();
      loadMachineGeometries();
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const [leftWidth, setLeftWidth] = useState(440);
  const panelsRef = useRef<HTMLDivElement>(null);
  const isResizingLeft = useRef(false);
  const resizeStartX = useRef(0);
  const resizeStartW = useRef(0);

  const onLeftResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizingLeft.current = true;
    resizeStartX.current = e.clientX;
    resizeStartW.current = leftWidth;
    panelsRef.current?.setAttribute("data-resizing", "true");
  }, [leftWidth]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isResizingLeft.current) return;
      const delta = e.clientX - resizeStartX.current;
      setLeftWidth(Math.max(200, Math.min(800, resizeStartW.current + delta)));
    };
    const onUp = () => {
      if (!isResizingLeft.current) return;
      isResizingLeft.current = false;
      panelsRef.current?.removeAttribute("data-resizing");
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  return (
    <div className="app-shell">
      <Header />
      <NiceStatusBar />
      <PlaybackScrubber />
      <div
        className="panels"
        ref={panelsRef}
        style={{ "--left-w": `${leftWidth}px` } as React.CSSProperties}
      >
        <LeftPanel />
        <div className="panels-resize-handle" onMouseDown={onLeftResizeStart} />
        <RightPanel />
      </div>
      <SettingsModal />
      <WaveformViewer />
    </div>
  );
}
