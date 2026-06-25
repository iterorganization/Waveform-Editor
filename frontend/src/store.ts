import { create } from "zustand";
import { api } from "./api";
import type {
  GapDefinition,
  MachineGeometries,
  NiceIntervalConfig,
  ParsedConfig,
  SettingsData,
  TendencyInfo,
  TimestepResult,
  WsMessage,
} from "./types";

// Default YAML with NICE Shape and Properties sections
export const DEFAULT_YAML = `globals:
  dd_version: 4.0.0
  machine_description: {}

NICE Shape:
  kappa:
  - {type: constant, value: 1.8, duration: 100}
  delta:
  - {type: constant, value: 0.43, duration: 100}
  a:
  - {type: constant, value: 1.9, duration: 100}
  center_r:
  - {type: constant, value: 6.2, duration: 100}
  center_z:
  - {type: constant, value: 0.545, duration: 100}
  rx:
  - {type: constant, value: 5.089, duration: 100}
  zx:
  - {type: constant, value: -3.346, duration: 100}

NICE Properties:
  ip:
  - {type: constant, value: -15000000, duration: 100}
  b0:
  - {type: constant, value: -5.3, duration: 100}
  r0:
  - {type: constant, value: 6.2, duration: 100}
  profile_alpha:
  - {type: constant, value: 0.5, duration: 100}
  profile_beta:
  - {type: constant, value: 0.5, duration: 100}
  profile_gamma:
  - {type: constant, value: 1.0, duration: 100}
`;

interface AppState {
  // YAML content
  yamlContent: string;
  debouncedYamlContent: string; // 400 ms trailing debounce — use for API calls in components
  parsedConfig: ParsedConfig | null;
  yamlError: string;
  yamlAnnotations: string[]; // waveform-level warnings/errors from the library
  yamlHistory: string[];    // undo/redo snapshots
  yamlHistoryIndex: number; // current position in yamlHistory

  // Settings
  settings: SettingsData;
  showSettings: boolean;

  // Machine geometries (loaded from IMAS on settings change)
  machineGeometries: MachineGeometries | null;
  machineLoading: boolean;

  // NICE interval config
  niceInterval: NiceIntervalConfig;

  // NICE run state
  niceRunning: boolean;
  niceStatus: string;
  niceProgress: { current: number; total: number };
  results: TimestepResult[];  // ordered by timestep index

  // Shape preview (input waveforms evaluated over time, always available)
  shapePreviewData: { times: number[]; waveforms: Record<string, number[]> } | null;
  shapePreviewIndex: number;

  // Playback
  currentResultIndex: number;
  isPlaying: boolean;
  playbackFps: number;

  // Shape editor
  shapeEditorMode: "params" | "gaps";
  shapeGaps: GapDefinition[];
  shapeGapUri: string;
  showShapeEditor: boolean;

  // UI
  expandedLaneId: string | null;
  showAdvancedEditor: boolean;
  activeComparisonTab: number;
  viewerWaveformName: string | null;

  // Tendency metadata cache, refreshed in the same round trip as each parse
  tendenciesCache: Record<string, TendencyInfo[]>;
  tendencyErrors: Record<string, string>;

  // Actions
  setYamlContent: (yaml: string) => void;
  undo: () => void;
  redo: () => void;
  parseCurrentYaml: () => Promise<void>;
  setSettings: (s: SettingsData) => void;
  setShowSettings: (v: boolean) => void;
  loadMachineGeometries: () => Promise<void>;
  setNiceInterval: (cfg: Partial<NiceIntervalConfig>) => void;
  /** Run NICE. With explicit timesteps, results merge into the existing set
   *  (replacing same-time results) instead of starting fresh. */
  runNice: (timesteps?: number[]) => void;
  stopNice: () => void;
  setShapePreviewIndex: (idx: number) => void;
  /** Register waveform names whose tendencies the UI needs (kept fresh by parseCurrentYaml) */
  addTendencyWatch: (names: string[]) => void;
  removeTendencyWatch: (names: string[]) => void;
  setCurrentResultIndex: (i: number) => void;
  setIsPlaying: (v: boolean) => void;
  setPlaybackFps: (fps: number) => void;
  setExpandedLane: (id: string | null) => void;
  setShowAdvancedEditor: (v: boolean) => void;
  setActiveComparisonTab: (tab: number) => void;
  openWaveformViewer: (name: string) => void;
  closeWaveformViewer: () => void;
  loadSettingsFromServer: () => Promise<void>;
  setShapeEditorMode: (mode: "params" | "gaps") => void;
  setShapeGapUri: (uri: string) => void;
  loadShapeGaps: (uri: string, time: number) => Promise<string>;
  setShowShapeEditor: (v: boolean) => void;
}

let wsRef: WebSocket | null = null;
let playbackTimer: ReturnType<typeof setInterval> | null = null;
let debouncedYamlTimer: ReturnType<typeof setTimeout> | null = null;
let historyPushTimer: ReturnType<typeof setTimeout> | null = null;

// Refcounted set of waveform names whose tendencies the UI currently needs.
// Not in the store state: only the resulting tendenciesCache is rendered.
const tendencyWatch = new Map<string, number>();
const watchedTendencyNames = () => [...tendencyWatch.keys()];
// Guards against out-of-order sync responses (fast consecutive edits)
let syncSeq = 0;

/** Index of the latest NICE result computed at or before time t, or -1 if none */
export function latestResultIndexAtTime(results: TimestepResult[], t: number): number {
  let best = -1;
  for (let i = 0; i < results.length; i++) {
    if (results[i].t <= t + 1e-9 && (best < 0 || results[i].t >= results[best].t)) best = i;
  }
  return best;
}

/** Index of the preview time closest to t (preview times are ascending) */
function previewIndexForTime(times: number[], t: number): number {
  let best = 0;
  for (let i = 0; i < times.length; i++) {
    if (Math.abs(times[i] - t) < Math.abs(times[best] - t)) best = i;
  }
  return best;
}

export const useStore = create<AppState>((set, get) => ({
  yamlContent: DEFAULT_YAML,
  debouncedYamlContent: DEFAULT_YAML,
  parsedConfig: null,
  yamlError: "",
  yamlAnnotations: [],
  yamlHistory: [DEFAULT_YAML],
  yamlHistoryIndex: 0,

  settings: {
    nice_inv_executable: "nice_imas_inv_muscle3",
    nice_dir_executable: "nice_imas_dir_muscle3",
    nice_mode: "NICE Inverse",
    machine_preset: "Custom",
    md_pf_active: "",
    md_pf_passive: "",
    md_wall: "",
    md_iron_core: "",
    verbose: 1,
    environment: {},
  },
  showSettings: false,

  machineGeometries: null,
  machineLoading: false,

  niceInterval: { rangeStart: null, rangeEnd: null, nPoints: 11, warmStart: true },

  niceRunning: false,
  niceStatus: "",
  niceProgress: { current: 0, total: 0 },
  results: [],

  shapePreviewData: null,
  shapePreviewIndex: 0,

  currentResultIndex: 0,
  isPlaying: false,
  playbackFps: 60,

  shapeEditorMode: "params",
  shapeGaps: [],
  shapeGapUri: "",
  showShapeEditor: false,

  expandedLaneId: null,
  showAdvancedEditor: false,
  activeComparisonTab: 0,
  viewerWaveformName: null,
  tendenciesCache: {},
  tendencyErrors: {},

  // ── Actions ──────────────────────────────────────────────────────────────────

  setYamlContent: (yaml) => {
    set({ yamlContent: yaml });
    if (debouncedYamlTimer) clearTimeout(debouncedYamlTimer);
    debouncedYamlTimer = setTimeout(() => set({ debouncedYamlContent: yaml }), 400);
    if (historyPushTimer) clearTimeout(historyPushTimer);
    historyPushTimer = setTimeout(() => {
      historyPushTimer = null;
      const { yamlHistory, yamlHistoryIndex } = get();
      if (yamlHistory[yamlHistoryIndex] === yaml) return;
      const next = [...yamlHistory.slice(0, yamlHistoryIndex + 1), yaml].slice(-100);
      set({ yamlHistory: next, yamlHistoryIndex: next.length - 1 });
    }, 600);
  },

  undo: () => {
    if (historyPushTimer) { clearTimeout(historyPushTimer); historyPushTimer = null; }
    const { yamlContent, yamlHistory, yamlHistoryIndex } = get();
    let history = yamlHistory;
    let index = yamlHistoryIndex;
    // Flush any uncommitted state before undoing
    if (yamlContent !== history[index]) {
      history = [...history.slice(0, index + 1), yamlContent].slice(-100);
      index = history.length - 1;
      set({ yamlHistory: history, yamlHistoryIndex: index });
    }
    if (index <= 0) return;
    const prev = history[index - 1];
    set({ yamlContent: prev, debouncedYamlContent: prev, yamlHistoryIndex: index - 1 });
    get().parseCurrentYaml();
  },

  redo: () => {
    const { yamlHistory, yamlHistoryIndex } = get();
    if (yamlHistoryIndex >= yamlHistory.length - 1) return;
    const next = yamlHistory[yamlHistoryIndex + 1];
    set({ yamlContent: next, debouncedYamlContent: next, yamlHistoryIndex: yamlHistoryIndex + 1 });
    get().parseCurrentYaml();
  },

  parseCurrentYaml: async () => {
    const { yamlContent } = get();
    const seq = ++syncSeq;
    try {
      // One round trip: parse + preview evaluation + tendencies for all
      // waveforms the UI is watching. Critical for high-latency (SSH) links.
      const r = await api.sync(yamlContent, watchedTendencyNames());
      if (seq !== syncSeq) return; // a newer sync is in flight — drop stale result
      set((s) => {
        const base = {
          parsedConfig: r.parsed,
          yamlError: r.parsed.load_error,
          yamlAnnotations: r.parsed.annotations ?? [],
          tendenciesCache: r.tendencies,
          tendencyErrors: r.tendency_errors,
        };
        if (r.parsed.load_error) return base;
        if (!r.times.length || !Object.keys(r.values).length) {
          return { ...base, shapePreviewData: null };
        }
        // Keep the scrub position across preview reloads (e.g. after a shape
        // edit) by mapping the previous time onto the new time grid.
        const oldT = s.shapePreviewData?.times[s.shapePreviewIndex];
        return {
          ...base,
          shapePreviewData: { times: r.times, waveforms: r.values },
          shapePreviewIndex: oldT != null ? previewIndexForTime(r.times, oldT) : 0,
        };
      });
    } catch (e) {
      if (seq === syncSeq) set({ yamlError: String(e) });
    }
  },

  addTendencyWatch: (names) => {
    const missing: string[] = [];
    for (const n of names) {
      tendencyWatch.set(n, (tendencyWatch.get(n) ?? 0) + 1);
      const s = get();
      if (!(n in s.tendenciesCache) && !(n in s.tendencyErrors)) missing.push(n);
    }
    // Names not covered by the last sync: fetch once, batched
    if (missing.length && get().parsedConfig) {
      api.getTendenciesBatch(get().yamlContent, missing)
        .then((r) => set((s) => ({
          tendenciesCache: { ...s.tendenciesCache, ...r.tendencies },
          tendencyErrors: { ...s.tendencyErrors, ...r.tendency_errors },
        })))
        .catch(() => {});
    }
  },

  removeTendencyWatch: (names) => {
    for (const n of names) {
      const c = tendencyWatch.get(n);
      if (c === undefined) continue;
      if (c <= 1) tendencyWatch.delete(n);
      else tendencyWatch.set(n, c - 1);
    }
  },

  setSettings: async (s) => {
    set({ settings: s });
    try {
      await api.saveSettings(s);
    } catch (_) {}
  },

  setShowSettings: (v) => set({ showSettings: v }),

  loadMachineGeometries: async () => {
    const { settings } = get();
    if (!settings.md_pf_active && !settings.md_wall) return;
    set({ machineLoading: true });
    try {
      const geo = await api.getMachineGeometries(
        settings.md_pf_active,
        settings.md_wall,
      );
      set({ machineGeometries: geo });
    } catch (e) {
      console.error("Failed to load machine geometries:", e);
    } finally {
      set({ machineLoading: false });
    }
  },

  setNiceInterval: (cfg) =>
    set((s) => ({ niceInterval: { ...s.niceInterval, ...cfg } })),

  runNice: (explicitTs?: number[]) => {
    const state = get();
    if (state.niceRunning) return;

    // Compute timesteps: N linearly spaced points over the selected region
    // (or the full timeline when no region is set)
    const { parsedConfig, niceInterval, settings, yamlContent } = state;
    const tStart = parsedConfig?.time_start ?? 0;
    const tEnd = parsedConfig?.time_end ?? 100;
    const t0 = niceInterval.rangeStart ?? tStart;
    const t1 = niceInterval.rangeEnd ?? tEnd;
    const n = Math.max(1, Math.round(niceInterval.nPoints));
    const linspaceTs = n === 1
      ? [parseFloat(((t0 + t1) / 2).toFixed(6))]
      : Array.from({ length: n }, (_, i) =>
          parseFloat((t0 + (i / (n - 1)) * (t1 - t0)).toFixed(6)));
    const allTs = explicitTs?.length
      ? [...explicitTs].sort((a, b) => a - b)
      : Array.from(new Set(linspaceTs)).sort((a, b) => a - b);

    // Explicit-timestep runs refine the existing result set; range runs start fresh
    set({
      niceRunning: true,
      ...(explicitTs?.length ? {} : { results: [] }),
      niceStatus: "Connecting...",
      niceProgress: { current: 0, total: allTs.length },
    });

    const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${wsProtocol}://${window.location.host}/ws/nice`);
    wsRef = ws;

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          yaml_content: yamlContent,
          timesteps: allTs,
          n_bnd_points: 96,
          // Warm start is sequential — off whenever multiple workers run
          warm_start: niceInterval.warmStart && (niceInterval.parallelWorkers ?? 1) === 1,
          parallel_workers: niceInterval.parallelWorkers ?? 1, // 0 = auto (all cores)
          shape_mode: state.shapeEditorMode,
          gap_definitions: state.shapeGaps,
          nice_mode: settings.nice_mode,
          inv_executable: settings.nice_inv_executable,
          dir_executable: settings.nice_dir_executable,
          environment: settings.environment,
          md_pf_active_uri: settings.md_pf_active,
          md_pf_passive_uri: settings.md_pf_passive,
          md_wall_uri: settings.md_wall,
          md_iron_core_uri: settings.md_iron_core,
          verbose: settings.verbose,
        }),
      );
    };

    ws.onmessage = (ev) => {
      let msg: WsMessage;
      try {
        msg = JSON.parse(ev.data as string);
      } catch (err) {
        // e.g. NaN in the payload — surface it instead of losing the timestep
        console.warn("Failed to parse NICE websocket message:", err, ev.data);
        set({ niceStatus: "Warning: a malformed result message was skipped" });
        return;
      }
      if (msg.type === "status") {
        set({ niceStatus: msg.message });
      } else if (msg.type === "error") {
        set({ niceRunning: false, niceStatus: `Error: ${msg.message}` });
      } else if (msg.type === "started") {
        const workers = msg.workers ?? 1;
        set({
          niceStatus: workers > 1 ? `Running NICE (${workers} parallel workers)...` : "Running NICE...",
          niceProgress: { current: 0, total: msg.total },
        });
      } else if (msg.type === "timestep_result") {
        const result = msg as unknown as TimestepResult;
        set((s) => {
          // Merge by time (replaces an existing result at the same t) and keep
          // sorted, so single-timestep runs refine the set instead of appending
          const others = s.results.filter((r) => Math.abs(r.t - result.t) > 1e-9);
          const merged = [...others, result].sort((a, b) => a.t - b.t);
          return {
            results: merged,
            // Count received results — with parallel workers they arrive out of
            // order, so result.index is not a progress indicator
            niceProgress: { current: Math.min(s.niceProgress.current + 1, result.total), total: result.total },
            currentResultIndex: merged.indexOf(result),  // auto-advance to latest
            // Keep the preview scrubber following the run
            ...(s.shapePreviewData
              ? { shapePreviewIndex: previewIndexForTime(s.shapePreviewData.times, result.t) }
              : {}),
          };
        });
      } else if (msg.type === "completed") {
        set({ niceRunning: false, niceStatus: `Done — ${msg.total} timesteps completed` });
        wsRef = null;
      }
    };

    ws.onerror = () => {
      set({ niceRunning: false, niceStatus: "WebSocket error" });
      wsRef = null;
    };

    ws.onclose = () => {
      if (get().niceRunning) {
        set({ niceRunning: false, niceStatus: "Connection closed" });
      }
      wsRef = null;
    };
  },

  stopNice: () => {
    if (wsRef) {
      wsRef.close();
      wsRef = null;
    }
    if (playbackTimer) {
      clearInterval(playbackTimer);
      playbackTimer = null;
    }
    set({ niceRunning: false, isPlaying: false, niceStatus: "Stopped" });
  },

  setShapePreviewIndex: (idx) => set((s) => {
    const t = s.shapePreviewData?.times[idx];
    // Scrubbing the full timeline also selects which NICE result to display:
    // the latest one computed at or before the current time.
    return {
      shapePreviewIndex: idx,
      ...(s.results.length && t != null
        ? { currentResultIndex: latestResultIndexAtTime(s.results, t) }
        : {}),
    };
  }),

  setCurrentResultIndex: (i) => set({ currentResultIndex: i }),

  setIsPlaying: (v) => {
    if (v) {
      const step = () => {
        const { results, currentResultIndex, shapePreviewData, shapePreviewIndex } = get();
        // Playback always walks the full preview timeline (the NICE result shown
        // alongside is derived from the current time). Results-only stepping is a
        // fallback for when there is no preview data.
        if (shapePreviewData) {
          if (shapePreviewIndex >= shapePreviewData.times.length - 1) {
            set({ isPlaying: false });
            if (playbackTimer) { clearInterval(playbackTimer); playbackTimer = null; }
            return;
          }
          get().setShapePreviewIndex(shapePreviewIndex + 1);
        } else if (results.length > 0) {
          if (currentResultIndex >= results.length - 1) {
            set({ isPlaying: false });
            if (playbackTimer) { clearInterval(playbackTimer); playbackTimer = null; }
            return;
          }
          set({ currentResultIndex: currentResultIndex + 1 });
        }
      };
      if (playbackTimer) { clearInterval(playbackTimer); playbackTimer = null; }
      playbackTimer = setInterval(step, 1000 / get().playbackFps);
      set({ isPlaying: true });
    } else {
      if (playbackTimer) { clearInterval(playbackTimer); playbackTimer = null; }
      set({ isPlaying: false });
    }
  },

  setPlaybackFps: (fps) => {
    const clamped = Math.max(1, Math.min(60, fps));
    set({ playbackFps: clamped });
    if (get().isPlaying) {
      // restart timer at new rate — reuse setIsPlaying to avoid duplicating step logic
      get().setIsPlaying(false);
      get().setIsPlaying(true);
    }
  },

  setExpandedLane: (id) => set({ expandedLaneId: id }),
  setShowAdvancedEditor: (v) => set({ showAdvancedEditor: v }),
  setActiveComparisonTab: (tab) => set({ activeComparisonTab: tab }),
  openWaveformViewer: (name) => set({ viewerWaveformName: name }),
  closeWaveformViewer: () => set({ viewerWaveformName: null }),
  setShapeEditorMode: (mode) => set({ shapeEditorMode: mode }),
  setShapeGapUri: (uri) => set({ shapeGapUri: uri }),
  loadShapeGaps: async (uri, time) => {
    try {
      const resp = await api.loadShapeGaps(uri, time);
      if (resp.error) return resp.error;
      set({ shapeGaps: resp.gaps, shapeGapUri: uri });
      return "";
    } catch (e) {
      return String(e);
    }
  },
  setShowShapeEditor: (v) => set({ showShapeEditor: v }),

  loadSettingsFromServer: async () => {
    try {
      const s = await api.getSettings();
      set({ settings: s });
    } catch (_) {}
  },
}));

// Returns a point count that gives ≥20 samples per period for the shortest
// sine/square/triangle wave in the YAML, clamped to [minN, maxN].
export function adaptivePoints(yaml: string, duration: number, minN: number, maxN: number): number {
  const periodRe = /\bperiod\s*:\s*([0-9.eE+\-]+)/g;
  const freqRe = /\bfrequency\s*:\s*([0-9.eE+\-]+)/g;
  let minPeriod = duration; // fallback: no oscillation → uniform spacing
  for (const m of yaml.matchAll(periodRe)) {
    const p = parseFloat(m[1]);
    if (p > 0) minPeriod = Math.min(minPeriod, p);
  }
  for (const m of yaml.matchAll(freqRe)) {
    const f = parseFloat(m[1]);
    if (f > 0) minPeriod = Math.min(minPeriod, 1 / f);
  }
  const needed = Math.ceil((duration / minPeriod) * 20);
  return Math.min(maxN, Math.max(minN, needed));
}
