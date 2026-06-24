import { create } from "zustand";
import { api } from "./api";
import type {
  MachineGeometries,
  NiceIntervalConfig,
  ParsedConfig,
  SettingsData,
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
  - {type: linear, from: 0, to: -15000000, duration: 100}
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
  parsedConfig: ParsedConfig | null;
  yamlError: string;

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

  // UI
  expandedLaneId: string | null;
  showAdvancedEditor: boolean;
  activeComparisonTab: number;

  // Actions
  setYamlContent: (yaml: string) => void;
  parseCurrentYaml: () => Promise<void>;
  setSettings: (s: SettingsData) => void;
  setShowSettings: (v: boolean) => void;
  loadMachineGeometries: () => Promise<void>;
  setNiceInterval: (cfg: Partial<NiceIntervalConfig>) => void;
  runNice: () => void;
  stopNice: () => void;
  setShapePreviewIndex: (idx: number) => void;
  evaluateShapePreview: () => Promise<void>;
  setCurrentResultIndex: (i: number) => void;
  setIsPlaying: (v: boolean) => void;
  setExpandedLane: (id: string | null) => void;
  setShowAdvancedEditor: (v: boolean) => void;
  setActiveComparisonTab: (tab: number) => void;
  loadSettingsFromServer: () => Promise<void>;
}

let wsRef: WebSocket | null = null;
let playbackTimer: ReturnType<typeof setInterval> | null = null;

export const useStore = create<AppState>((set, get) => ({
  yamlContent: DEFAULT_YAML,
  parsedConfig: null,
  yamlError: "",

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

  niceInterval: { uniformStep: 10, extraTimesteps: [] },

  niceRunning: false,
  niceStatus: "",
  niceProgress: { current: 0, total: 0 },
  results: [],

  shapePreviewData: null,
  shapePreviewIndex: 0,

  currentResultIndex: 0,
  isPlaying: false,

  expandedLaneId: null,
  showAdvancedEditor: false,
  activeComparisonTab: 0,

  // ── Actions ──────────────────────────────────────────────────────────────────

  setYamlContent: (yaml) => {
    set({ yamlContent: yaml });
  },

  parseCurrentYaml: async () => {
    const { yamlContent } = get();
    try {
      const parsed = await api.parseYaml(yamlContent);
      set({ parsedConfig: parsed, yamlError: parsed.load_error });
      if (!parsed.load_error) get().evaluateShapePreview();
    } catch (e) {
      set({ yamlError: String(e) });
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

  runNice: () => {
    const state = get();
    if (state.niceRunning) return;

    // Compute timesteps
    const { parsedConfig, niceInterval, settings, yamlContent } = state;
    const tStart = parsedConfig?.time_start ?? 0;
    const tEnd = parsedConfig?.time_end ?? 100;
    const step = niceInterval.uniformStep;

    const uniformTs: number[] = [];
    for (let t = tStart; t <= tEnd + 1e-9; t += step) {
      uniformTs.push(parseFloat(t.toFixed(6)));
    }
    const allTs = Array.from(
      new Set([...uniformTs, ...niceInterval.extraTimesteps]),
    ).sort((a, b) => a - b);

    set({ niceRunning: true, results: [], niceStatus: "Connecting...", niceProgress: { current: 0, total: allTs.length } });

    const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${wsProtocol}://${window.location.host}/ws/nice`);
    wsRef = ws;

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          yaml_content: yamlContent,
          timesteps: allTs,
          n_bnd_points: 96,
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
      const msg: WsMessage = JSON.parse(ev.data as string);
      if (msg.type === "status") {
        set({ niceStatus: msg.message });
      } else if (msg.type === "error") {
        set({ niceRunning: false, niceStatus: `Error: ${msg.message}` });
      } else if (msg.type === "started") {
        set({ niceStatus: "Running NICE...", niceProgress: { current: 0, total: msg.total } });
      } else if (msg.type === "timestep_result") {
        const result = msg as unknown as TimestepResult;
        set((s) => ({
          results: [...s.results, result],
          niceProgress: { current: result.index + 1, total: result.total },
          currentResultIndex: s.results.length,  // auto-advance to latest
        }));
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

  setShapePreviewIndex: (idx) => set({ shapePreviewIndex: idx }),

  evaluateShapePreview: async () => {
    const { yamlContent, parsedConfig } = get();
    if (!parsedConfig || parsedConfig.load_error) return;
    const tStart = parsedConfig.time_start;
    const tEnd = parsedConfig.time_end;
    if (tEnd <= tStart) return;
    const n = 120;
    const times = Array.from({ length: n }, (_, i) => tStart + (i / (n - 1)) * (tEnd - tStart));
    try {
      const resp = await api.evaluateWaveforms(yamlContent, times, ["kappa", "delta", "a", "center_r", "center_z"]);
      const waveforms: Record<string, number[]> = {};
      for (const wf of resp.waveforms) waveforms[wf.name] = wf.values;
      set(Object.keys(waveforms).length > 0
        ? { shapePreviewData: { times, waveforms }, shapePreviewIndex: 0 }
        : { shapePreviewData: null });
    } catch (_) {}
  },

  setCurrentResultIndex: (i) => set({ currentResultIndex: i }),

  setIsPlaying: (v) => {
    if (v) {
      const step = () => {
        const { results, currentResultIndex, shapePreviewData, shapePreviewIndex } = get();
        if (results.length > 0) {
          if (currentResultIndex >= results.length - 1) {
            set({ isPlaying: false });
            if (playbackTimer) { clearInterval(playbackTimer); playbackTimer = null; }
            return;
          }
          set({ currentResultIndex: currentResultIndex + 1 });
        } else if (shapePreviewData) {
          if (shapePreviewIndex >= shapePreviewData.times.length - 1) {
            set({ isPlaying: false });
            if (playbackTimer) { clearInterval(playbackTimer); playbackTimer = null; }
            return;
          }
          set({ shapePreviewIndex: shapePreviewIndex + 1 });
        }
      };
      playbackTimer = setInterval(step, 150);
      set({ isPlaying: true });
    } else {
      if (playbackTimer) { clearInterval(playbackTimer); playbackTimer = null; }
      set({ isPlaying: false });
    }
  },

  setExpandedLane: (id) => set({ expandedLaneId: id }),
  setShowAdvancedEditor: (v) => set({ showAdvancedEditor: v }),
  setActiveComparisonTab: (tab) => set({ activeComparisonTab: tab }),

  loadSettingsFromServer: async () => {
    try {
      const s = await api.getSettings();
      set({ settings: s });
    } catch (_) {}
  },
}));
