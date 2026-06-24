import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { WaveformLane } from "../../components/timeline/WaveformLane";
import { useStore } from "../../store";

vi.mock("../../api", () => ({
  api: {
    evaluateWaveforms: vi.fn().mockResolvedValue({
      waveforms: [{ name: "kappa", times: [0, 50, 100], values: [1.8, 1.8, 1.8] }],
      error: "",
    }),
    parseYaml: vi.fn().mockResolvedValue({ waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" }),
  },
}));

const CONSTANT_SPEC = [{ type: "constant" as const, duration: 100, value: 1.8 }];

beforeEach(() => {
  useStore.setState({
    expandedLaneId: null,
    parsedConfig: { waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" },
    yamlContent: "kappa:\n- {type: constant, value: 1.8, duration: 100}\n",
  });
});

afterEach(() => {
  vi.clearAllMocks();
});


describe("WaveformLane — rendering", () => {
  it("renders the waveform name", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    expect(screen.getByText("kappa")).toBeInTheDocument();
  });

  it("shows tendency count chip for array spec", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    expect(screen.getByText("1t")).toBeInTheDocument();
  });

  it("shows expr chip for derived spec", () => {
    render(<WaveformLane name="derived" spec={'"kappa" * 2'} />);
    expect(screen.getByText("expr")).toBeInTheDocument();
  });

  it("renders a sparkline svg", () => {
    const { container } = render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    expect(container.querySelector("svg.sparkline-svg")).not.toBeNull();
  });

  it("shows down arrow when collapsed", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    expect(screen.getByText("▼")).toBeInTheDocument();
  });
});


describe("WaveformLane — expand/collapse", () => {
  it("expands on click", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    fireEvent.click(screen.getByText("kappa").closest(".waveform-lane")!);
    expect(useStore.getState().expandedLaneId).toBe("kappa");
  });

  it("shows form when expanded", () => {
    useStore.setState({ expandedLaneId: "kappa" });
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    expect(screen.getByText("+ Add tendency")).toBeInTheDocument();
  });

  it("shows up arrow when expanded", () => {
    useStore.setState({ expandedLaneId: "kappa" });
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    expect(screen.getByText("▲")).toBeInTheDocument();
  });

  it("collapses on second click", () => {
    useStore.setState({ expandedLaneId: "kappa" });
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    fireEvent.click(screen.getByText("kappa").closest(".waveform-lane")!);
    expect(useStore.getState().expandedLaneId).toBeNull();
  });

  it("shows derived expression when expanded and spec is a string", () => {
    useStore.setState({ expandedLaneId: "derived" });
    render(<WaveformLane name="derived" spec={'"kappa" * 2'} />);
    expect(screen.getByText('"kappa" * 2')).toBeInTheDocument();
  });

  it("shows edit-in-advanced-mode hint for derived waveform", () => {
    useStore.setState({ expandedLaneId: "derived" });
    render(<WaveformLane name="derived" spec={'"kappa" * 2'} />);
    expect(screen.getByText(/Advanced.*YAML/)).toBeInTheDocument();
  });
});


// YAML with kappa indented inside a group, exactly as DEFAULT_YAML produces
const GROUPED_YAML = [
  "NICE Shape:",
  "  kappa:",
  "  - {type: constant, value: 1.8, duration: 100}",
  "  delta:",
  "  - {type: constant, value: 0.43, duration: 100}",
  "",
].join("\n");

describe("WaveformLane — YAML rebuild preserves group indentation", () => {
  beforeEach(() => {
    useStore.setState({
      expandedLaneId: "kappa",
      parsedConfig: { waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" },
      yamlContent: GROUPED_YAML,
    });
  });

  it("does not place waveform key at document root after adding a tendency", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    fireEvent.click(screen.getByText("+ Add tendency"));
    const { yamlContent } = useStore.getState();
    // kappa: must NOT appear at column 0 (that would break the group)
    const rootKappa = yamlContent.split("\n").find((l) => /^kappa:/.test(l));
    expect(rootKappa).toBeUndefined();
  });

  it("keeps the waveform indented inside its group after adding a tendency", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    fireEvent.click(screen.getByText("+ Add tendency"));
    const { yamlContent } = useStore.getState();
    expect(yamlContent).toMatch(/^\s+kappa:/m);
  });

  it("preserves sibling waveforms in the same group", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    fireEvent.click(screen.getByText("+ Add tendency"));
    const { yamlContent } = useStore.getState();
    expect(yamlContent).toContain("delta:");
  });

  it("appends the new tendency item in the rebuilt YAML", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    fireEvent.click(screen.getByText("+ Add tendency"));
    const { yamlContent } = useStore.getState();
    // Default new tendency has value: 0 and duration: 10
    expect(yamlContent).toContain("value: 0");
    expect(yamlContent).toContain("duration: 10");
  });

  it("sequence items are at same indentation as the key", () => {
    render(<WaveformLane name="kappa" spec={CONSTANT_SPEC} />);
    fireEvent.click(screen.getByText("+ Add tendency"));
    const { yamlContent } = useStore.getState();
    const lines = yamlContent.split("\n");
    const keyIdx = lines.findIndex((l) => /^\s+kappa:/.test(l));
    expect(keyIdx).toBeGreaterThanOrEqual(0);
    const keyIndent = lines[keyIdx].match(/^(\s*)/)?.[1] ?? "";
    const seqPrefix = `${keyIndent}- `;
    // Count only consecutive sequence items directly after kappa: (stop at sibling keys)
    let count = 0;
    for (let i = keyIdx + 1; i < lines.length && lines[i].startsWith(seqPrefix); i++) count++;
    // Should have original item + one new item
    expect(count).toBe(2);
  });
});


describe("WaveformLane — tendency count", () => {
  it("shows 0t for empty spec", () => {
    render(<WaveformLane name="wave" spec={[]} />);
    expect(screen.getByText("0t")).toBeInTheDocument();
  });

  it("shows 3t for three tendencies", () => {
    const spec = [
      { type: "constant" as const, duration: 10, value: 1 },
      { type: "constant" as const, duration: 10, value: 2 },
      { type: "constant" as const, duration: 10, value: 3 },
    ];
    render(<WaveformLane name="wave" spec={spec} />);
    expect(screen.getByText("3t")).toBeInTheDocument();
  });
});
