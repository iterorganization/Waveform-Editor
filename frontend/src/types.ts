// ── Data types mirroring the Python Pydantic models ───────────────────────────

export interface WaveformInfo {
  name: string;
  group_path: string[];
  is_derived: boolean;
}

export interface ParsedConfig {
  waveforms: WaveformInfo[];
  time_start: number;
  time_end: number;
  yaml_content: string;
  load_error: string;
}

export interface WaveformValues {
  name: string;
  times: number[];
  values: number[];
}

export interface EvaluateResponse {
  waveforms: WaveformValues[];
  error: string;
}

export interface CoilRect {
  r0: number; z0: number; r1: number; z1: number; name: string;
}

export interface CoilPath {
  r: number[]; z: number[]; name: string;
}

export interface WallPath {
  r: number[]; z: number[]; name: string;
}

export interface MachineGeometries {
  coil_rectangles: CoilRect[];
  coil_paths: CoilPath[];
  wall_limiter: WallPath[];
  vacuum_vessel: WallPath[];
  error: string;
}

export interface ContourSegment {
  x: number[]; y: number[]; psi: number;
}

export interface TimestepResult {
  t: number;
  index: number;
  total: number;
  status: "success" | "error" | "running";
  error?: string;
  contours: ContourSegment[];
  separatrix_r: number[];
  separatrix_z: number[];
  o_points: Array<{ r: number; z: number }>;
  x_points: Array<{ r: number; z: number }>;
  metrics: Record<string, number>;
  psi_norm: number[];
  dpressure_dpsi: number[];
  f_df_dpsi: number[];
  input_psi_norm: number[];
  input_dpressure_dpsi: number[];
  input_f_df_dpsi: number[];
  coil_names: string[];
  coil_currents: number[];
  input_values: Record<string, number>;
}

export interface SettingsData {
  nice_inv_executable: string;
  nice_dir_executable: string;
  nice_mode: string;
  machine_preset: string;
  md_pf_active: string;
  md_pf_passive: string;
  md_wall: string;
  md_iron_core: string;
  verbose: number;
  environment: Record<string, string>;
}

// ── Tendency types ─────────────────────────────────────────────────────────────

export type TendencyType =
  | "constant"
  | "linear"
  | "smooth"
  | "sine-wave"
  | "square-wave"
  | "sawtooth-wave"
  | "triangle-wave"
  | "piecewise"
  | "repeat";

export interface TendencyData {
  type: TendencyType;
  duration?: number;
  value?: number;
  from?: number;
  to?: number;
  base?: number;
  amplitude?: number;
  frequency?: number;
  phase?: number;
  [key: string]: unknown;
}

// A waveform is either a list of tendencies or a derived expression string
export type WaveformSpec = TendencyData[] | string;

// ── Hierarchical waveform tree for the UI ─────────────────────────────────────

export interface WaveformGroup {
  name: string;
  path: string[];
  groups: Record<string, WaveformGroup>;
  waveforms: Record<string, WaveformSpec>;
}

// ── WebSocket message shapes ───────────────────────────────────────────────────

export type WsMessage =
  | { type: "status"; message: string }
  | { type: "error"; message: string }
  | { type: "started"; total: number }
  | { type: "timestep_result" } & TimestepResult
  | { type: "completed"; total: number };

// ── NICE interval config ───────────────────────────────────────────────────────

export interface NiceIntervalConfig {
  uniformStep: number;
  extraTimesteps: number[];
}
