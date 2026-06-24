import { useStore } from "../../store";

export function PlaybackScrubber() {
  const {
    results, currentResultIndex, setCurrentResultIndex,
    shapePreviewData, shapePreviewIndex, setShapePreviewIndex,
    isPlaying, setIsPlaying,
  } = useStore();

  const hasNice = results.length > 0;
  const hasPreview = shapePreviewData != null;
  if (!hasNice && !hasPreview) return null;

  const count = hasNice ? results.length : (shapePreviewData?.times.length ?? 0);
  const index = hasNice ? currentResultIndex : shapePreviewIndex;
  const setIndex = hasNice ? setCurrentResultIndex : setShapePreviewIndex;
  const t = hasNice
    ? (results[currentResultIndex]?.t ?? 0)
    : (shapePreviewData?.times[shapePreviewIndex] ?? 0);

  return (
    <div className="scrubber">
      <button
        className="btn btn-sm"
        onClick={() => setIndex(Math.max(0, index - 1))}
        disabled={index === 0}
      >⏮</button>
      <button
        className="btn btn-sm"
        onClick={() => setIsPlaying(!isPlaying)}
      >
        {isPlaying ? "⏸" : "▶"}
      </button>
      <button
        className="btn btn-sm"
        onClick={() => setIndex(Math.min(count - 1, index + 1))}
        disabled={index >= count - 1}
      >⏭</button>
      <div className="scrubber-track">
        <input
          type="range"
          min={0}
          max={count - 1}
          value={index}
          onChange={(e) => setIndex(parseInt(e.target.value))}
        />
      </div>
      <span className="scrubber-time">{`t = ${t.toFixed(2)} s`}</span>
      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
        {index + 1} / {count}
      </span>
    </div>
  );
}
