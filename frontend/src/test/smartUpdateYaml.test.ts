import { describe, expect, it } from "vitest";
import { smartUpdateYaml } from "../components/shape-editor/ShapeEditorPanel";
import type { TendencyInfo } from "../types";

function td(partial: Partial<TendencyInfo>): TendencyInfo {
  return {
    index: 0,
    type: "constant",
    line_number: 2,
    start_time: 0,
    end_time: 100,
    params: {},
    ...partial,
  };
}

const HEADER = "NICE Shape:\n  kappa:\n";

describe("smartUpdateYaml — constant", () => {
  const yaml = HEADER + "  - {type: constant, value: 5, duration: 100}";
  const tds = [td({ type: "constant", params: { value: 5, duration: 100 } })];

  it("splits into two linears when edited mid-tendency", () => {
    const out = smartUpdateYaml(yaml, tds, 50, 7);
    const lines = out.split("\n");
    expect(lines[2]).toBe("  - {type: linear, from: 5, to: 7, duration: 50}");
    expect(lines[3]).toBe("  - {type: linear, from: 7, to: 5, duration: 50}");
    expect(lines).toHaveLength(4);
  });

  it("keeps segment durations summing to the original", () => {
    const out = smartUpdateYaml(yaml, tds, 30, 7);
    expect(out).toContain("duration: 30");
    expect(out).toContain("duration: 70");
  });

  it("becomes a single linear when edited at the start", () => {
    const out = smartUpdateYaml(yaml, tds, 0, 7);
    const lines = out.split("\n");
    expect(lines[2]).toBe("  - {type: linear, from: 7, to: 5, duration: 100}");
    expect(lines).toHaveLength(3);
  });

  it("becomes a single linear when edited at the end", () => {
    const out = smartUpdateYaml(yaml, tds, 100, 7);
    const lines = out.split("\n");
    expect(lines[2]).toBe("  - {type: linear, from: 5, to: 7, duration: 100}");
    expect(lines).toHaveLength(3);
  });
});

describe("smartUpdateYaml — time outside the waveform's range", () => {
  // Timeline spans the longest waveform; this one ends at t=50
  const yaml = HEADER + "  - {type: constant, value: 5, duration: 50}";
  const tds = [td({ type: "constant", end_time: 50, params: { value: 5, duration: 50 } })];

  it("appends a linear tendency when editing beyond the end", () => {
    const out = smartUpdateYaml(yaml, tds, 100, 7);
    const lines = out.split("\n");
    // Original tendency untouched; new linear reaches the new value at t=100
    expect(lines[2]).toBe("  - {type: constant, value: 5, duration: 50}");
    expect(lines[3]).toBe("  - {type: linear, from: 5, to: 7, duration: 50}");
    expect(lines).toHaveLength(4);
  });

  it("appended tendency uses the sampled last value for wave types", () => {
    const yaml2 = HEADER + "  - {type: sine, base: 2, amplitude: 1, period: 10, duration: 50}";
    const tds2 = [td({ type: "sine", end_time: 50, params: { base: 2, amplitude: 1, period: 10, duration: 50 } })];
    const sampled = { times: [0, 50], values: [2, 3] }; // wave ends at value 3
    const out = smartUpdateYaml(yaml2, tds2, 80, 5, sampled);
    expect(out.split("\n")[3]).toBe("  - {type: linear, from: 3, to: 5, duration: 30}");
  });

  it("clamps an edit before the start to the initial value", () => {
    const tds2 = [td({ type: "constant", start_time: 20, end_time: 50, params: { value: 5 } })];
    const out = smartUpdateYaml(yaml, tds2, 0, 7);
    expect(out.split("\n")[2]).toBe("  - {type: linear, from: 7, to: 5, duration: 30}");
  });

  it("appends after a linear using its `to` as the last value", () => {
    const yaml2 = HEADER + "  - {type: linear, from: 1, to: 3, duration: 50}";
    const tds2 = [td({ type: "linear", end_time: 50, params: { from: 1, to: 3, duration: 50 } })];
    const out = smartUpdateYaml(yaml2, tds2, 100, 9);
    const lines = out.split("\n");
    expect(lines[2]).toBe("  - {type: linear, from: 1, to: 3, duration: 50}");
    expect(lines[3]).toBe("  - {type: linear, from: 3, to: 9, duration: 50}");
  });

  it("returns unchanged for empty tendencies", () => {
    expect(smartUpdateYaml(yaml, [], 100, 7)).toBe(yaml);
  });
});

describe("smartUpdateYaml — linear", () => {
  const yaml = HEADER + "  - {type: linear, from: 1, to: 3, duration: 100}";
  const tds = [td({ type: "linear", params: { from: 1, to: 3, duration: 100 } })];

  it("splits preserving both endpoints when edited mid-tendency", () => {
    const out = smartUpdateYaml(yaml, tds, 50, 5);
    const lines = out.split("\n");
    expect(lines[2]).toBe("  - {type: linear, from: 1, to: 5, duration: 50}");
    expect(lines[3]).toBe("  - {type: linear, from: 5, to: 3, duration: 50}");
  });

  it("adjusts only `from` at the start", () => {
    const out = smartUpdateYaml(yaml, tds, 0, 5);
    expect(out.split("\n")[2]).toBe("  - {type: linear, from: 5, to: 3, duration: 100}");
  });

  it("adjusts only `to` at the end and cascades to the next tendency", () => {
    const yaml2 = HEADER
      + "  - {type: linear, from: 1, to: 3, duration: 50}\n"
      + "  - {type: linear, from: 3, to: 0, duration: 50}";
    const tds2 = [
      td({ type: "linear", line_number: 2, start_time: 0, end_time: 50, params: { from: 1, to: 3, duration: 50 } }),
      td({ type: "linear", line_number: 3, start_time: 50, end_time: 100, params: { from: 3, to: 0, duration: 50 } }),
    ];
    const out = smartUpdateYaml(yaml2, tds2, 50, 4);
    const lines = out.split("\n");
    // t=50 falls in the first tendency (end) — its `to` moves, and the next `from` follows
    expect(lines[2]).toBe("  - {type: linear, from: 1, to: 4, duration: 50}");
    expect(lines[3]).toBe("  - {type: linear, from: 4, to: 0, duration: 50}");
  });

  it("resolves implied from/to via sampled data when params are missing", () => {
    const yaml2 = HEADER + "  - {type: linear, to: 3, duration: 100}";
    const tds2 = [td({ type: "linear", params: { to: 3, duration: 100 } })];
    const sampled = { times: [0, 100], values: [1, 3] };
    const out = smartUpdateYaml(yaml2, tds2, 50, 5, sampled);
    const lines = out.split("\n");
    expect(lines[2]).toBe("  - {type: linear, from: 1, to: 5, duration: 50}");
    expect(lines[3]).toBe("  - {type: linear, from: 5, to: 3, duration: 50}");
  });
});

describe("smartUpdateYaml — smooth", () => {
  it("splits into two smooths", () => {
    const yaml = HEADER + "  - {type: smooth, from: 1, to: 3, duration: 100}";
    const tds = [td({ type: "smooth", params: { from: 1, to: 3, duration: 100 } })];
    const out = smartUpdateYaml(yaml, tds, 50, 5);
    const lines = out.split("\n");
    expect(lines[2]).toBe("  - {type: smooth, from: 1, to: 5, duration: 50}");
    expect(lines[3]).toBe("  - {type: smooth, from: 5, to: 3, duration: 50}");
  });
});

describe("smartUpdateYaml — sine wave", () => {
  it("scales amplitude to match the new value away from zero crossings", () => {
    const yaml = HEADER + "  - {type: sine-wave, base: 2, amplitude: 1, frequency: 0.05, duration: 100}";
    const tds = [td({ type: "sine-wave", params: { base: 2, amplitude: 1, frequency: 0.05, duration: 100 } })];
    // At t=5, sin(2π·0.05·5) = sin(π/2) = 1 → wave value = 3 (peak)
    const sampled = { times: [5], values: [3] };
    const out = smartUpdateYaml(yaml, tds, 5, 4, sampled);
    // g = (3-2)/1 = 1 → new amplitude = (4-2)/1 = 2
    expect(out.split("\n")[2]).toContain("amplitude: 2");
    expect(out.split("\n")[2]).toContain("base: 2");
  });

  it("shifts base instead near a zero crossing", () => {
    const yaml = HEADER + "  - {type: sine-wave, base: 2, amplitude: 1, frequency: 0.05, duration: 100}";
    const tds = [td({ type: "sine-wave", params: { base: 2, amplitude: 1, frequency: 0.05, duration: 100 } })];
    // At t=0 the sine is at its base (zero crossing): old value = 2, g = 0
    const sampled = { times: [0], values: [2] };
    const out = smartUpdateYaml(yaml, tds, 0, 3, sampled);
    expect(out.split("\n")[2]).toContain("base: 3");
    expect(out.split("\n")[2]).toContain("amplitude: 1");
  });

  it("recognises the `sine` alias with min/max/period style", () => {
    // Style from the ITER flat-top dataset: {type: sine, min: 1.68, max: 1.72, period: 100, ...}
    const yaml = HEADER + "  - {type: sine, min: 1.68, max: 1.72, period: 100, duration: 500}";
    const tds = [td({
      type: "sine",
      start_time: 0, end_time: 500,
      params: { min: 1.68, max: 1.72, period: 100, duration: 500 },
    })];
    // At t=25 (quarter period) the sine is at its max 1.72; base=1.70, amp=0.02
    const sampled = { times: [25], values: [1.72] };
    const out = smartUpdateYaml(yaml, tds, 25, 1.8, sampled);
    const line = out.split("\n")[2];
    // g=1 → new amplitude = 1.8 - 1.7 = 0.1
    expect(line).toContain("base: 1.7");
    expect(line).toContain("amplitude: 0.1");
    expect(line).toContain("period: 100");
    expect(line).not.toContain("min:");
  });

  it("converts min/max style to base/amplitude", () => {
    const yaml = HEADER + "  - {type: sine-wave, min: 1, max: 3, frequency: 0.05, duration: 100}";
    const tds = [td({ type: "sine-wave", params: { min: 1, max: 3, frequency: 0.05, duration: 100 } })];
    const sampled = { times: [5], values: [3] }; // at peak, base=2 amp=1
    const out = smartUpdateYaml(yaml, tds, 5, 4, sampled);
    const line = out.split("\n")[2];
    expect(line).not.toContain("min:");
    expect(line).not.toContain("max:");
    expect(line).toContain("base: 2");
    expect(line).toContain("amplitude: 2");
  });
});

describe("smartUpdateYaml — piecewise", () => {
  it("updates an existing point", () => {
    const yaml = HEADER + "  - {type: piecewise, time: [0, 50, 100], value: [1, 2, 3]}";
    const tds = [td({
      type: "piecewise",
      params: {},
      piecewise_times: [0, 50, 100],
      piecewise_values: [1, 2, 3],
    })];
    const out = smartUpdateYaml(yaml, tds, 50, 9);
    expect(out.split("\n")[2]).toBe("  - {type: piecewise, time: [0, 50, 100], value: [1, 9, 3]}");
  });
});
