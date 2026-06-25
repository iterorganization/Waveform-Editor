import { useCallback, useEffect, useMemo, useRef } from "react";
import { useStore } from "../store";

export function RunNiceModal({ onClose }: { onClose: () => void }) {
  const { niceInterval, setNiceInterval, parsedConfig, runNice } = useStore();
  const overlayRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ mode: "new" | "start" | "end"; anchor: number } | null>(null);

  const tStart = parsedConfig?.time_start ?? 0;
  const tEnd = parsedConfig?.time_end ?? 100;
  const range = tEnd - tStart || 1;

  const t0 = niceInterval.rangeStart ?? tStart;
  const t1 = niceInterval.rangeEnd ?? tEnd;
  const n = Math.max(1, Math.round(niceInterval.nPoints));
  const workers = niceInterval.parallelWorkers ?? 1; // 0 = auto (all cores)
  const autoCores = workers === 0;
  const parallel = autoCores || workers > 1;

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const toPct = (t: number) => ((t - tStart) / range) * 100;
  const timeAtClientX = useCallback((clientX: number) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return tStart;
    const frac = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return tStart + frac * range;
  }, [tStart, range]);

  // ── Region selection: drag on the track to select, drag handles to adjust ──
  const beginDrag = useCallback((e: React.MouseEvent, mode: "new" | "start" | "end") => {
    e.preventDefault();
    e.stopPropagation();
    const t = timeAtClientX(e.clientX);
    dragRef.current = { mode, anchor: mode === "new" ? t : (mode === "start" ? t1 : t0) };
    if (mode === "new") setNiceInterval({ rangeStart: t, rangeEnd: t });
  }, [timeAtClientX, t0, t1, setNiceInterval]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      const t = timeAtClientX(e.clientX);
      const lo = Math.min(drag.anchor, t);
      const hi = Math.max(drag.anchor, t);
      setNiceInterval({ rangeStart: lo, rangeEnd: hi });
    };
    const onUp = () => { dragRef.current = null; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [timeAtClientX, setNiceInterval]);

  const resetRegion = () => setNiceInterval({ rangeStart: null, rangeEnd: null });

  // The timesteps that will run
  const allTs = useMemo(() => {
    if (n === 1) return [(t0 + t1) / 2];
    return Array.from({ length: n }, (_, i) => t0 + (i / (n - 1)) * (t1 - t0));
  }, [t0, t1, n]);

  const handleRun = () => { runNice(); onClose(); };
  const fullRange = niceInterval.rangeStart == null && niceInterval.rangeEnd == null;

  return (
    <div
      className="modal-overlay"
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="modal run-nice-modal">
        <div className="modal-header">
          <span className="modal-title">Run NICE</span>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {/* ── Region selector ─────────────────────────────────────────── */}
          <div className="rn-region-label">
            <span>Time region — drag on the timeline to select</span>
            {!fullRange && (
              <button className="btn btn-sm" onClick={resetRegion} title="Reset to the full timeline">
                Full range
              </button>
            )}
          </div>
          <div
            className="rn-region-track"
            ref={trackRef}
            onMouseDown={(e) => beginDrag(e, "new")}
            onDoubleClick={resetRegion}
            title="Drag to select a region · double-click to reset"
          >
            <div className="rn-region-axis" />
            <div
              className="rn-region-band"
              style={{ left: `${toPct(t0)}%`, width: `${Math.max(0.3, toPct(t1) - toPct(t0))}%` }}
            />
            {allTs.map((t, i) => (
              <div key={i} className="rn-region-tick" style={{ left: `${toPct(t)}%` }} />
            ))}
            <div
              className="rn-region-handle"
              style={{ left: `${toPct(t0)}%` }}
              onMouseDown={(e) => beginDrag(e, "start")}
            />
            <div
              className="rn-region-handle"
              style={{ left: `${toPct(t1)}%` }}
              onMouseDown={(e) => beginDrag(e, "end")}
            />
          </div>
          <div className="rn-region-scale">
            <span>{tStart.toFixed(1)} s</span>
            <span>{tEnd.toFixed(1)} s</span>
          </div>

          {/* ── Numeric fine-tuning: label sits above its own input ───────── */}
          <div className="rn-fields">
            <label className="rn-field">
              <span>From (s)</span>
              <input
                type="number" step="any"
                value={parseFloat(t0.toFixed(3))}
                onChange={(e) => {
                  const v = parseFloat(e.target.value);
                  if (!isNaN(v)) setNiceInterval({ rangeStart: Math.min(v, t1) });
                }}
                className="rn-input rn-input-sm"
              />
            </label>
            <label className="rn-field">
              <span>To (s)</span>
              <input
                type="number" step="any"
                value={parseFloat(t1.toFixed(3))}
                onChange={(e) => {
                  const v = parseFloat(e.target.value);
                  if (!isNaN(v)) setNiceInterval({ rangeEnd: Math.max(v, t0) });
                }}
                className="rn-input rn-input-sm"
              />
            </label>
            <label className="rn-field">
              <span>Timesteps</span>
              <input
                type="number" min={1} max={500} step={1}
                value={n}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  if (!isNaN(v)) setNiceInterval({ nPoints: Math.max(1, Math.min(500, v)) });
                }}
                className="rn-input rn-input-sm"
              />
            </label>
          </div>
          <div className="rn-hint">
            {n} linearly spaced timestep{n === 1 ? "" : "s"} over {t0.toFixed(2)} → {t1.toFixed(2)} s
            {n > 1 && ` (Δt = ${((t1 - t0) / (n - 1)).toFixed(2)} s)`}
          </div>

          <div className="rn-row">
            <label className="rn-label" htmlFor="rn-workers">Parallel</label>
            <input
              id="rn-workers"
              type="number" min={1} max={64} step={1}
              value={autoCores ? "" : workers}
              disabled={autoCores}
              placeholder={autoCores ? "auto" : undefined}
              onChange={(e) => {
                const v = parseInt(e.target.value);
                if (!isNaN(v)) setNiceInterval({ parallelWorkers: Math.max(1, Math.min(64, v)) });
              }}
              className="rn-input rn-input-sm"
            />
            <label className="rn-hint" style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <input
                type="checkbox"
                checked={autoCores}
                onChange={(e) => setNiceInterval({ parallelWorkers: e.target.checked ? 0 : 1 })}
              />
              all available cores
            </label>
            <span className="rn-hint">
              {autoCores
                ? "one NICE instance per CPU core of the server"
                : workers > 1
                  ? `${workers} NICE instances run contiguous chunks of ~${Math.ceil(allTs.length / workers)} timesteps concurrently`
                  : "NICE instances running timesteps concurrently"}
            </span>
          </div>

          <div className="rn-row">
            <label className="rn-label" htmlFor="rn-warm-start">Warm start</label>
            <input
              id="rn-warm-start"
              type="checkbox"
              checked={niceInterval.warmStart && !parallel}
              disabled={parallel}
              onChange={(e) => setNiceInterval({ warmStart: e.target.checked })}
            />
            <span className="rn-hint">
              {parallel
                ? "Disabled for parallel runs — warm starting is sequential by nature"
                : "Use each timestep's converged equilibrium as the initial guess for the " +
                  "next one (improves convergence; falls back to cold start after a failed step)"}
            </span>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-sm" onClick={onClose}>Cancel</button>
          <button className="btn btn-sm btn-success" onClick={handleRun}>
            ▶ Run NICE ({allTs.length} steps)
          </button>
        </div>
      </div>
    </div>
  );
}
