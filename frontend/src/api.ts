import type {
  EvaluateResponse,
  MachineGeometries,
  ParsedConfig,
  SettingsData,
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
};
