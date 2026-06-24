/**
 * Tests for the API client module — verifies that the correct fetch calls
 * are made and that responses are returned to the caller.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";

function makeFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    statusText: ok ? "OK" : "Not Found",
    json: () => Promise.resolve(body),
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", makeFetch({}));
});

afterEach(() => {
  vi.unstubAllGlobals();
});


describe("api.getSettings", () => {
  it("calls GET /api/settings", async () => {
    const mockFetch = makeFetch({ nice_mode: "NICE Inverse" });
    vi.stubGlobal("fetch", mockFetch);
    await api.getSettings();
    expect(mockFetch).toHaveBeenCalledWith("/api/settings");
  });

  it("returns the parsed JSON", async () => {
    const settings = { nice_inv_executable: "nice", verbose: 2, environment: {} };
    vi.stubGlobal("fetch", makeFetch(settings));
    const result = await api.getSettings();
    expect(result).toEqual(settings);
  });
});


describe("api.saveSettings", () => {
  it("calls POST /api/settings with the data", async () => {
    const mockFetch = makeFetch({ ok: true });
    vi.stubGlobal("fetch", mockFetch);
    const payload = {
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
    };
    await api.saveSettings(payload);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/settings",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("throws on non-OK response", async () => {
    vi.stubGlobal("fetch", makeFetch({ detail: "Server error" }, false, 500));
    await expect(api.saveSettings({} as never)).rejects.toThrow("500");
  });
});


describe("api.parseYaml", () => {
  it("calls POST /api/yaml/parse with the yaml_content", async () => {
    const mockFetch = makeFetch({ waveforms: [], load_error: "" });
    vi.stubGlobal("fetch", mockFetch);
    await api.parseYaml("some: yaml");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/yaml/parse",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ yaml_content: "some: yaml" }),
      }),
    );
  });

  it("returns parsed config with waveforms", async () => {
    const response = {
      waveforms: [{ name: "kappa", group_path: ["NICE Shape"], is_derived: false }],
      time_start: 0,
      time_end: 100,
      yaml_content: "",
      load_error: "",
    };
    vi.stubGlobal("fetch", makeFetch(response));
    const result = await api.parseYaml("y");
    expect(result.waveforms).toHaveLength(1);
    expect(result.waveforms[0].name).toBe("kappa");
  });
});


describe("api.evaluateWaveforms", () => {
  it("calls POST /api/waveform/evaluate with correct body", async () => {
    const mockFetch = makeFetch({ waveforms: [], error: "" });
    vi.stubGlobal("fetch", mockFetch);
    await api.evaluateWaveforms("yaml", [0, 1, 2], ["kappa"]);
    const [, opts] = mockFetch.mock.calls[0];
    const body = JSON.parse(opts.body as string);
    expect(body.yaml_content).toBe("yaml");
    expect(body.time_points).toEqual([0, 1, 2]);
    expect(body.waveform_names).toEqual(["kappa"]);
  });

  it("sends undefined waveform_names when not specified", async () => {
    const mockFetch = makeFetch({ waveforms: [], error: "" });
    vi.stubGlobal("fetch", mockFetch);
    await api.evaluateWaveforms("yaml", [0]);
    const [, opts] = mockFetch.mock.calls[0];
    const body = JSON.parse(opts.body as string);
    expect(body.waveform_names).toBeUndefined();
  });
});


describe("api.getMachineGeometries", () => {
  it("calls POST /api/machine/geometries", async () => {
    const mockFetch = makeFetch({ coil_rectangles: [], coil_paths: [], wall_limiter: [], vacuum_vessel: [], error: "" });
    vi.stubGlobal("fetch", mockFetch);
    await api.getMachineGeometries("imas:hdf5?path=/pf_active", "imas:hdf5?path=/wall");
    const [path, opts] = mockFetch.mock.calls[0];
    expect(path).toBe("/api/machine/geometries");
    const body = JSON.parse(opts.body as string);
    expect(body.md_pf_active_uri).toBe("imas:hdf5?path=/pf_active");
    expect(body.md_wall_uri).toBe("imas:hdf5?path=/wall");
  });
});


describe("error handling", () => {
  it("throws when server returns 404", async () => {
    vi.stubGlobal("fetch", makeFetch({}, false, 404));
    await expect(api.parseYaml("y")).rejects.toThrow("404");
  });
});
