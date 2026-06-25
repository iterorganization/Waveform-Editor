import type {
  EvaluateResponse,
  GapDefinition,
  GapsResponse,
  InverseMillerResponse,
  MachineGeometries,
  ParsedConfig,
  SettingsData,
  ShapeOutlineResponse,
  SyncResponse,
  TendenciesBatchResponse,
  TendenciesResponse,
} from "./types";

const BASE = "/api";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  getSettings: () => get<SettingsData>("/settings"),

  saveSettings: (data: SettingsData) =>
    post<{ ok: boolean }>("/settings", data),

  parseYaml: (yaml_content: string) =>
    post<ParsedConfig>("/yaml/parse", { yaml_content }),

  evaluateWaveforms: (
    yaml_content: string,
    time_points: number[],
    waveform_names?: string[],
  ) =>
    post<EvaluateResponse>("/waveform/evaluate", {
      yaml_content,
      time_points,
      waveform_names,
    }),

  getMachineGeometries: (md_pf_active_uri: string, md_wall_uri: string) =>
    post<MachineGeometries>("/machine/geometries", {
      md_pf_active_uri,
      md_wall_uri,
    }),

  getTendencies: (yaml_content: string, waveform_name: string) =>
    post<TendenciesResponse>("/waveform/tendencies", { yaml_content, waveform_name }),

  getTendenciesBatch: (yaml_content: string, waveform_names: string[]) =>
    post<TendenciesBatchResponse>("/waveform/tendencies_batch", { yaml_content, waveform_names }),

  /** Parse + evaluate preview + tendencies in a single round trip */
  sync: (yaml_content: string, tendency_names: string[], min_points = 200, max_points = 2000) =>
    post<SyncResponse>("/yaml/sync", { yaml_content, tendency_names, min_points, max_points }),

  loadShapeGaps: (uri: string, time: number) =>
    post<GapsResponse>("/shape/gaps", { uri, time }),

  getShapeOutline: (
    yaml_content: string,
    time: number,
    mode: "params" | "gaps",
    gap_waveform_names: string[],
    gap_definitions: GapDefinition[],
  ) =>
    post<ShapeOutlineResponse>("/shape/outline", {
      yaml_content, time, mode, gap_waveform_names, gap_definitions,
    }),

  inverseMillerFit: (
    current_params: Record<string, number>,
    drag_r: number,
    drag_z: number,
    theta: number,
  ) =>
    post<InverseMillerResponse>("/shape/inverse_miller", {
      current_params, drag_r, drag_z, theta,
    }),
};
