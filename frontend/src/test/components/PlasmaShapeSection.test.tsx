import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PlasmaShapeSection } from "../../components/timeline/PlasmaShapeSection";
import { useStore } from "../../store";

vi.mock("../../api", () => ({
  api: {
    evaluateWaveforms: vi.fn().mockResolvedValue({ waveforms: [], error: "" }),
  },
}));

const SHAPE_NAMES = ["kappa", "delta", "a", "center_r", "center_z", "rx", "zx"];

function parsedConfigWith(names: string[]) {
  return {
    waveforms: names.map((n) => ({ name: n, group_path: ["NICE Shape"], is_derived: false })),
    time_start: 0,
    time_end: 100,
    yaml_content: "",
    load_error: "",
  };
}

beforeEach(() => {
  useStore.setState({
    parsedConfig: null,
    expandedLaneId: null,
    yamlContent: "",
  });
});


describe("PlasmaShapeSection — header", () => {
  it("renders section title", () => {
    render(<PlasmaShapeSection />);
    expect(screen.getByText(/Plasma Shape/)).toBeInTheDocument();
  });

  it("shows 0/7 badge when no waveforms defined", () => {
    render(<PlasmaShapeSection />);
    expect(screen.getByText("0/7")).toBeInTheDocument();
  });

  it("shows 7/7 badge when all shape waveforms defined", () => {
    useStore.setState({ parsedConfig: parsedConfigWith(SHAPE_NAMES) });
    render(<PlasmaShapeSection />);
    expect(screen.getByText("7/7")).toBeInTheDocument();
  });

  it("shows partial count correctly", () => {
    useStore.setState({ parsedConfig: parsedConfigWith(["kappa", "delta", "a"]) });
    render(<PlasmaShapeSection />);
    expect(screen.getByText("3/7")).toBeInTheDocument();
  });
});


describe("PlasmaShapeSection — lane rendering", () => {
  it("shows 'not defined' placeholders when no waveforms configured", () => {
    render(<PlasmaShapeSection />);
    const notDefined = screen.getAllByText("not defined");
    expect(notDefined).toHaveLength(7);
  });

  it("shows WaveformLane for defined waveforms", () => {
    useStore.setState({ parsedConfig: parsedConfigWith(["kappa"]) });
    const { container } = render(<PlasmaShapeSection />);
    // kappa renders as a WaveformLane — its lane-name span should be present
    const laneNames = container.querySelectorAll(".lane-name");
    const kappaLane = Array.from(laneNames).find((el) => el.textContent === "kappa");
    expect(kappaLane).toBeDefined();
  });

  it("shows 6 'not defined' when only kappa is defined", () => {
    useStore.setState({ parsedConfig: parsedConfigWith(["kappa"]) });
    render(<PlasmaShapeSection />);
    const notDefined = screen.getAllByText("not defined");
    expect(notDefined).toHaveLength(6);
  });

  it("renders all params as lanes when all are defined", () => {
    useStore.setState({ parsedConfig: parsedConfigWith(SHAPE_NAMES) });
    const { container } = render(<PlasmaShapeSection />);
    const laneNames = Array.from(container.querySelectorAll(".lane-name")).map((el) => el.textContent);
    for (const name of SHAPE_NAMES) {
      expect(laneNames).toContain(name);
    }
    expect(screen.queryByText("not defined")).toBeNull();
  });

  it("shows help text for YAML configuration", () => {
    render(<PlasmaShapeSection />);
    expect(screen.getByText(/kappa/)).toBeInTheDocument();
    expect(screen.getByText(/delta/)).toBeInTheDocument();
  });
});


describe("PlasmaShapeSection — collapse", () => {
  it("collapses body on header click", () => {
    const { container } = render(<PlasmaShapeSection />);
    const header = container.querySelector(".section-header")!;
    fireEvent.click(header);
    expect(container.querySelector(".section-body")).toBeNull();
  });

  it("expands on second click", () => {
    const { container } = render(<PlasmaShapeSection />);
    const header = container.querySelector(".section-header")!;
    fireEvent.click(header);
    fireEvent.click(header);
    expect(container.querySelector(".section-body")).not.toBeNull();
  });
});
