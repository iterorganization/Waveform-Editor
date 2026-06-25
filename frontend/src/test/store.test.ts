/**
 * Tests for the Zustand store — state shape, synchronous actions, and
 * the timestep computation logic inside runNice().
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStore, DEFAULT_YAML } from "../store";

// ── Mock the API so async store actions don't hit the network ────────────────────
vi.mock("../api", () => ({
  api: {
    parseYaml: vi.fn().mockResolvedValue({
      waveforms: [{ name: "kappa", group_path: ["NICE Shape"], is_derived: false }],
      time_start: 0,
      time_end: 100,
      yaml_content: "",
      load_error: "",
    }),
    sync: vi.fn().mockResolvedValue({
      parsed: {
        waveforms: [{ name: "kappa", group_path: ["NICE Shape"], is_derived: false }],
        time_start: 0,
        time_end: 100,
        yaml_content: "",
        load_error: "",
      },
      times: [0, 50, 100],
      values: { kappa: [1.8, 1.8, 1.8] },
      tendencies: {},
      tendency_errors: {},
    }),
    getTendenciesBatch: vi.fn().mockResolvedValue({ tendencies: {}, tendency_errors: {} }),
    saveSettings: vi.fn().mockResolvedValue({ ok: true }),
    getSettings: vi.fn().mockResolvedValue({
      nice_inv_executable: "nice",
      nice_dir_executable: "nice_dir",
      nice_mode: "NICE Inverse",
      machine_preset: "Custom",
      md_pf_active: "",
      md_pf_passive: "",
      md_wall: "",
      md_iron_core: "",
      verbose: 1,
      environment: {},
    }),
    getMachineGeometries: vi.fn().mockResolvedValue({
      coil_rectangles: [],
      coil_paths: [],
      wall_limiter: [],
      vacuum_vessel: [],
      error: "",
    }),
  },
}));

// ── Mock WebSocket ────────────────────────────────────────────────────────────────
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    // Simulate immediate open
    Promise.resolve().then(() => this.onopen?.(new Event("open")));
  }

  send(data: string) { this.sent.push(data); }
  close() { this.onclose?.({} as CloseEvent); }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
  // Reset store to clean baseline
  useStore.setState({
    yamlContent: DEFAULT_YAML,
    parsedConfig: null,
    yamlError: "",
    niceRunning: false,
    niceStatus: "",
    niceProgress: { current: 0, total: 0 },
    results: [],
    currentResultIndex: 0,
    isPlaying: false,
    expandedLaneId: null,
    showAdvancedEditor: false,
    activeComparisonTab: 0,
    showSettings: false,
    machineGeometries: null,
    machineLoading: false,
    niceInterval: { rangeStart: null, rangeEnd: null, nPoints: 11, warmStart: true },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});


// ── Initial state ─────────────────────────────────────────────────────────────────

describe("initial state", () => {
  it("has the default YAML content", () => {
    expect(useStore.getState().yamlContent).toBe(DEFAULT_YAML);
  });

  it("starts with no results", () => {
    expect(useStore.getState().results).toEqual([]);
  });

  it("starts with NICE not running", () => {
    expect(useStore.getState().niceRunning).toBe(false);
  });

  it("has default NICE interval (full range, 11 points)", () => {
    expect(useStore.getState().niceInterval.rangeStart).toBeNull();
    expect(useStore.getState().niceInterval.rangeEnd).toBeNull();
    expect(useStore.getState().niceInterval.nPoints).toBe(11);
  });

  it("has default settings", () => {
    const { settings } = useStore.getState();
    expect(settings.nice_inv_executable).toBe("nice_imas_inv_muscle3");
    expect(settings.nice_mode).toBe("NICE Inverse");
    expect(settings.verbose).toBe(1);
  });
});


// ── Synchronous actions ───────────────────────────────────────────────────────────

describe("setYamlContent", () => {
  it("updates yamlContent", () => {
    useStore.getState().setYamlContent("new: yaml");
    expect(useStore.getState().yamlContent).toBe("new: yaml");
  });
});

describe("setNiceInterval", () => {
  it("updates nPoints", () => {
    useStore.getState().setNiceInterval({ nPoints: 25 });
    expect(useStore.getState().niceInterval.nPoints).toBe(25);
  });

  it("updates the region", () => {
    useStore.getState().setNiceInterval({ rangeStart: 15.0, rangeEnd: 37.5 });
    expect(useStore.getState().niceInterval.rangeStart).toBe(15.0);
    expect(useStore.getState().niceInterval.rangeEnd).toBe(37.5);
  });

  it("merges partial updates", () => {
    useStore.getState().setNiceInterval({ nPoints: 5 });
    useStore.getState().setNiceInterval({ rangeStart: 42.0 });
    const { niceInterval } = useStore.getState();
    expect(niceInterval.nPoints).toBe(5);
    expect(niceInterval.rangeStart).toBe(42.0);
  });
});

describe("setCurrentResultIndex", () => {
  it("updates currentResultIndex", () => {
    useStore.getState().setCurrentResultIndex(3);
    expect(useStore.getState().currentResultIndex).toBe(3);
  });
});

describe("setExpandedLane", () => {
  it("sets the expanded lane id", () => {
    useStore.getState().setExpandedLane("kappa");
    expect(useStore.getState().expandedLaneId).toBe("kappa");
  });

  it("clears with null", () => {
    useStore.getState().setExpandedLane("kappa");
    useStore.getState().setExpandedLane(null);
    expect(useStore.getState().expandedLaneId).toBeNull();
  });
});

describe("setShowAdvancedEditor", () => {
  it("toggles the advanced editor flag", () => {
    useStore.getState().setShowAdvancedEditor(true);
    expect(useStore.getState().showAdvancedEditor).toBe(true);
    useStore.getState().setShowAdvancedEditor(false);
    expect(useStore.getState().showAdvancedEditor).toBe(false);
  });
});

describe("setActiveComparisonTab", () => {
  it("updates the active tab", () => {
    useStore.getState().setActiveComparisonTab(2);
    expect(useStore.getState().activeComparisonTab).toBe(2);
  });
});

describe("stopNice", () => {
  it("sets niceRunning to false", () => {
    useStore.setState({ niceRunning: true });
    useStore.getState().stopNice();
    expect(useStore.getState().niceRunning).toBe(false);
  });

  it("sets isPlaying to false", () => {
    useStore.setState({ isPlaying: true });
    useStore.getState().stopNice();
    expect(useStore.getState().isPlaying).toBe(false);
  });

  it("sets niceStatus to Stopped", () => {
    useStore.getState().stopNice();
    expect(useStore.getState().niceStatus).toBe("Stopped");
  });
});


// ── setIsPlaying with fake timers ─────────────────────────────────────────────────

describe("setIsPlaying", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("sets isPlaying to true when v=true", () => {
    useStore.setState({ results: [makeResult(0), makeResult(1), makeResult(2)] });
    useStore.getState().setIsPlaying(true);
    expect(useStore.getState().isPlaying).toBe(true);
  });

  it("advances currentResultIndex on timer tick", () => {
    useStore.setState({
      results: [makeResult(0), makeResult(1), makeResult(2)],
      currentResultIndex: 0,
      playbackFps: 10, // 100 ms per frame
    });
    useStore.getState().setIsPlaying(true);
    vi.advanceTimersByTime(100);
    expect(useStore.getState().currentResultIndex).toBe(1);
    vi.advanceTimersByTime(100);
    expect(useStore.getState().currentResultIndex).toBe(2);
  });

  it("stops at last result and sets isPlaying false", () => {
    useStore.setState({
      results: [makeResult(0), makeResult(1)],
      currentResultIndex: 1,
    });
    useStore.getState().setIsPlaying(true);
    vi.advanceTimersByTime(150);
    expect(useStore.getState().isPlaying).toBe(false);
  });

  it("sets isPlaying to false when v=false", () => {
    useStore.setState({ results: [makeResult(0), makeResult(1)] });
    useStore.getState().setIsPlaying(true);
    useStore.getState().setIsPlaying(false);
    expect(useStore.getState().isPlaying).toBe(false);
  });
});


// ── runNice timestep computation ──────────────────────────────────────────────────

describe("runNice", () => {
  it("sets niceRunning to true", async () => {
    useStore.setState({
      parsedConfig: { waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" },
      niceInterval: { rangeStart: null, rangeEnd: null, nPoints: 11, warmStart: true },
    });
    useStore.getState().runNice();
    expect(useStore.getState().niceRunning).toBe(true);
  });

  it("sends correct timesteps to WebSocket for 0-100 with step 10", async () => {
    useStore.setState({
      parsedConfig: { waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" },
      niceInterval: { rangeStart: null, rangeEnd: null, nPoints: 11, warmStart: true },
    });
    useStore.getState().runNice();

    // Wait for the open event to fire
    await Promise.resolve();

    const ws = MockWebSocket.instances[0];
    expect(ws).toBeDefined();
    expect(ws.sent.length).toBe(1);
    const payload = JSON.parse(ws.sent[0]);
    expect(payload.timesteps).toHaveLength(11); // 0,10,20,...,100
    expect(payload.timesteps[0]).toBe(0);
    expect(payload.timesteps[10]).toBe(100);
  });

  it("spaces timesteps linearly over the selected region", async () => {
    useStore.setState({
      parsedConfig: { waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" },
      niceInterval: { rangeStart: 20, rangeEnd: 60, nPoints: 3, warmStart: true },
    });
    useStore.getState().runNice();
    await Promise.resolve();

    const ws = MockWebSocket.instances[0];
    const payload = JSON.parse(ws.sent[0]);
    expect(payload.timesteps).toEqual([20, 40, 60]);
  });

  it("runs a single timestep at the region midpoint when nPoints is 1", async () => {
    useStore.setState({
      parsedConfig: { waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" },
      niceInterval: { rangeStart: 10, rangeEnd: 30, nPoints: 1, warmStart: true },
    });
    useStore.getState().runNice();
    await Promise.resolve();

    const ws = MockWebSocket.instances[0];
    const payload = JSON.parse(ws.sent[0]);
    expect(payload.timesteps).toEqual([20]);
  });

  it("does not start if already running", () => {
    useStore.setState({ niceRunning: true });
    useStore.getState().runNice();
    expect(MockWebSocket.instances.length).toBe(0);
  });

  it("resets results on new run", async () => {
    useStore.setState({
      parsedConfig: { waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" },
      niceInterval: { rangeStart: null, rangeEnd: null, nPoints: 2, warmStart: true },
      results: [makeResult(0)],
    });
    useStore.getState().runNice();
    expect(useStore.getState().results).toEqual([]);
  });

  it("updates results when timestep_result message received", async () => {
    useStore.setState({
      parsedConfig: { waveforms: [], time_start: 0, time_end: 10, yaml_content: "", load_error: "" },
      niceInterval: { rangeStart: null, rangeEnd: null, nPoints: 11, warmStart: true },
    });
    useStore.getState().runNice();
    await Promise.resolve();

    const ws = MockWebSocket.instances[0];
    ws.simulateMessage({
      type: "timestep_result",
      t: 0.0, index: 0, total: 2, status: "success",
      contours: [], separatrix_r: [], separatrix_z: [],
      o_points: [], x_points: [], metrics: {},
      psi_norm: [], dpressure_dpsi: [], f_df_dpsi: [],
      input_psi_norm: [], input_dpressure_dpsi: [], input_f_df_dpsi: [],
      coil_names: [], coil_currents: [], input_values: {},
    });

    expect(useStore.getState().results).toHaveLength(1);
    expect(useStore.getState().results[0].t).toBe(0.0);
  });

  it("sets niceRunning false on completed message", async () => {
    useStore.setState({
      parsedConfig: { waveforms: [], time_start: 0, time_end: 10, yaml_content: "", load_error: "" },
      niceInterval: { rangeStart: null, rangeEnd: null, nPoints: 11, warmStart: true },
    });
    useStore.getState().runNice();
    await Promise.resolve();

    const ws = MockWebSocket.instances[0];
    ws.simulateMessage({ type: "completed", total: 2 });

    expect(useStore.getState().niceRunning).toBe(false);
  });
});


// ── Helpers ───────────────────────────────────────────────────────────────────────

function makeResult(index: number): import("../types").TimestepResult {
  return {
    t: index * 10,
    index,
    total: 3,
    status: "success",
    contours: [],
    separatrix_r: [],
    separatrix_z: [],
    o_points: [],
    x_points: [],
    metrics: {},
    psi_norm: [],
    dpressure_dpsi: [],
    f_df_dpsi: [],
    input_psi_norm: [],
    input_dpressure_dpsi: [],
    input_f_df_dpsi: [],
    coil_names: [],
    coil_currents: [],
    input_values: {},
  };
}
