import { useStore } from "../../store";

export function PlaybackScrubber() {
  const {
    results, currentResultIndex, setCurrentResultIndex,
    shapePreviewData, shapePreviewIndex, setShapePreviewIndex,
    isPlaying, setIsPlaying,
    playbackFps, setPlaybackFps,
  } = useStore();

  const hasNice = results.length > 0;
  const hasPreview = shapePreviewData != null;
  if (!hasNice && !hasPreview) return null;

  // The scrubber always spans the full preview timeline when available, so the
  // desired shape stays browsable between (and beyond) computed NICE timesteps.
  // Results-only mode is a fallback when there is no preview data.
  const count = hasPreview ? shapePreviewData.times.length : results.length;
  const index = hasPreview ? shapePreviewIndex : currentResultIndex;
  const setIndex = hasPreview ? setShapePreviewIndex : setCurrentResultIndex;
  const t = hasPreview
    ? (shapePreviewData.times[shapePreviewIndex] ?? 0)
    : (results[currentResultIndex]?.t ?? 0);

  // NICE markers on the timeline (preview mode only — the range spans full time)
  const tMin = hasPreview ? shapePreviewData.times[0] : 0;
  const tMax = hasPreview ? shapePreviewData.times[shapePreviewData.times.length - 1] : 1;
  const tRange = tMax - tMin || 1;
  const toPct = (time: number) => ((time - tMin) / tRange) * 100;
  const niceTimes = hasPreview && hasNice ? results.map((r) => r.t) : [];
  const activeResult = hasNice ? results[currentResultIndex] : undefined;

  return (
    <div className="scrubber">
      <button className="btn btn-sm" onClick={() => setIndex(0)}              disabled={index === 0}          title="First frame">⏮</button>
      <button className="btn btn-sm" onClick={() => setIndex(index - 1)}      disabled={index === 0}          title="Previous frame">«</button>
      <button className="btn btn-sm" onClick={() => setIsPlaying(!isPlaying)}                                 title={isPlaying ? "Pause" : "Play"}>{isPlaying ? "⏸" : "▶"}</button>
      <button className="btn btn-sm" onClick={() => setIndex(index + 1)}      disabled={index >= count - 1}  title="Next frame">»</button>
      <button className="btn btn-sm" onClick={() => setIndex(count - 1)}      disabled={index >= count - 1}  title="Last frame">⏭</button>
      <div className="scrubber-track">
        <input
          type="range"
          min={0}
          max={count - 1}
          value={index}
          onChange={(e) => setIndex(parseInt(e.target.value))}
        />
        {niceTimes.length > 0 && (
          <div className="scrubber-markers">
            {/* Band covering the computed portion of the timeline */}
            <div
              className="scrubber-nice-band"
              style={{
                left: `${toPct(Math.min(...niceTimes))}%`,
                width: `${Math.max(0.5, toPct(Math.max(...niceTimes)) - toPct(Math.min(...niceTimes)))}%`,
              }}
            />
            {results.map((r, i) => (
              <div
                key={i}
                className={`scrubber-marker${i === currentResultIndex ? " active" : ""}${r.status === "error" ? " error" : ""}`}
                style={{ left: `${toPct(r.t)}%` }}
                title={`NICE t = ${r.t.toFixed(2)} s${r.status === "error" ? " (failed)" : ""}`}
              />
            ))}
          </div>
        )}
      </div>
      <span className="scrubber-time">{`t = ${t.toFixed(2)} s`}</span>
      {hasNice && hasPreview && (
        <span style={{ fontSize: 11, color: "var(--text-muted)", whiteSpace: "nowrap" }}
          title={activeResult ? `Showing NICE result at t = ${activeResult.t.toFixed(2)} s` : "No NICE result at or before this time"}>
          {activeResult ? `NICE @ ${activeResult.t.toFixed(1)}s` : "no NICE yet"}
        </span>
      )}
      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
        {index + 1} / {count}
      </span>
      <label className="scrubber-fps-label">
        <input
          type="number"
          className="scrubber-fps-input"
          min={1}
          max={60}
          step={1}
          value={playbackFps}
          onChange={(e) => setPlaybackFps(parseInt(e.target.value) || 1)}
        />
        fps
      </label>
    </div>
  );
}
