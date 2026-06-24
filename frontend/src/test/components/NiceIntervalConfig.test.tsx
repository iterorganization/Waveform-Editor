import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NiceIntervalConfig } from "../../components/timeline/NiceIntervalConfig";
import { useStore } from "../../store";

vi.mock("../../api", () => ({
  api: {
    parseYaml: vi.fn().mockResolvedValue({ waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" }),
    evaluateWaveforms: vi.fn().mockResolvedValue({ waveforms: [], error: "" }),
  },
}));

beforeEach(() => {
  useStore.setState({
    niceInterval: { uniformStep: 10, extraTimesteps: [] },
    parsedConfig: null,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});


describe("NiceIntervalConfig — rendering", () => {
  it("renders the section header", () => {
    render(<NiceIntervalConfig />);
    expect(screen.getByText(/NICE Run Intervals/)).toBeInTheDocument();
  });

  it("shows timestep count badge", () => {
    render(<NiceIntervalConfig />);
    // t=0..100 step=10 → 11 timesteps
    expect(screen.getByText("11 timesteps")).toBeInTheDocument();
  });

  it("shows current uniform step value in input", () => {
    useStore.setState({ niceInterval: { uniformStep: 20, extraTimesteps: [] } });
    render(<NiceIntervalConfig />);
    const input = screen.getByDisplayValue("20");
    expect(input).toBeInTheDocument();
  });

  it("shows preview bar", () => {
    const { container } = render(<NiceIntervalConfig />);
    expect(container.querySelector(".timestep-preview")).not.toBeNull();
  });

  it("shows tick marks equal to timestep count", () => {
    const { container } = render(<NiceIntervalConfig />);
    const marks = container.querySelectorAll(".timestep-mark");
    expect(marks.length).toBe(11); // 0-100 step 10
  });
});


describe("NiceIntervalConfig — uniform step", () => {
  it("updates store when step changes", () => {
    render(<NiceIntervalConfig />);
    const input = screen.getByDisplayValue("10");
    fireEvent.change(input, { target: { value: "25" } });
    expect(useStore.getState().niceInterval.uniformStep).toBe(25);
  });

  it("falls back to 1 for empty/invalid input", () => {
    render(<NiceIntervalConfig />);
    const input = screen.getByDisplayValue("10");
    fireEvent.change(input, { target: { value: "" } });
    expect(useStore.getState().niceInterval.uniformStep).toBe(1);
  });

  it("badge updates when step changes", () => {
    render(<NiceIntervalConfig />);
    const input = screen.getByDisplayValue("10");
    fireEvent.change(input, { target: { value: "50" } });
    expect(screen.getByText("3 timesteps")).toBeInTheDocument(); // 0, 50, 100
  });
});


describe("NiceIntervalConfig — extra timesteps", () => {
  it("adds an extra timestep on + button click", () => {
    render(<NiceIntervalConfig />);
    const numInput = screen.getByPlaceholderText("t =…");
    fireEvent.change(numInput, { target: { value: "35" } });
    fireEvent.click(screen.getByText("+"));
    expect(useStore.getState().niceInterval.extraTimesteps).toContain(35);
  });

  it("adds extra timestep on Enter key", () => {
    render(<NiceIntervalConfig />);
    const numInput = screen.getByPlaceholderText("t =…");
    fireEvent.change(numInput, { target: { value: "42.5" } });
    fireEvent.keyDown(numInput, { key: "Enter" });
    expect(useStore.getState().niceInterval.extraTimesteps).toContain(42.5);
  });

  it("ignores non-numeric extra input", () => {
    render(<NiceIntervalConfig />);
    const numInput = screen.getByPlaceholderText("t =…");
    fireEvent.change(numInput, { target: { value: "abc" } });
    fireEvent.click(screen.getByText("+"));
    expect(useStore.getState().niceInterval.extraTimesteps).toHaveLength(0);
  });

  it("shows chip for added extra timestep", () => {
    useStore.setState({ niceInterval: { uniformStep: 10, extraTimesteps: [35.0] } });
    render(<NiceIntervalConfig />);
    expect(screen.getByText(/35s/)).toBeInTheDocument();
  });

  it("removes extra timestep when chip × is clicked", () => {
    useStore.setState({ niceInterval: { uniformStep: 10, extraTimesteps: [35.0] } });
    render(<NiceIntervalConfig />);
    const removeBtn = screen.getByText("35s").closest(".ts-chip")!.querySelector(".ts-chip-remove")!;
    fireEvent.click(removeBtn);
    expect(useStore.getState().niceInterval.extraTimesteps).not.toContain(35.0);
  });

  it("keeps timesteps sorted", () => {
    useStore.setState({ niceInterval: { uniformStep: 100, extraTimesteps: [75.0] } });
    render(<NiceIntervalConfig />);
    const numInput = screen.getByPlaceholderText("t =…");
    fireEvent.change(numInput, { target: { value: "25" } });
    fireEvent.click(screen.getByText("+"));
    const ts = useStore.getState().niceInterval.extraTimesteps;
    expect(ts[0]).toBe(25);
    expect(ts[1]).toBe(75);
  });

  it("deduplicates extra timesteps that match uniform steps", () => {
    render(<NiceIntervalConfig />);
    const numInput = screen.getByPlaceholderText("t =…");
    // 50 already in uniform steps (0,10,...,100)
    fireEvent.change(numInput, { target: { value: "50" } });
    fireEvent.click(screen.getByText("+"));
    // Store accepts it, but the allTs in the component deduplicates via Set
    // The badge count should not double-count
    expect(screen.getByText("11 timesteps")).toBeInTheDocument();
  });
});


describe("NiceIntervalConfig — section collapse", () => {
  it("collapses on header click", () => {
    const { container } = render(<NiceIntervalConfig />);
    const header = container.querySelector(".section-header")!;
    fireEvent.click(header);
    expect(container.querySelector(".nice-interval")).toBeNull();
  });

  it("expands again on second header click", () => {
    const { container } = render(<NiceIntervalConfig />);
    const header = container.querySelector(".section-header")!;
    fireEvent.click(header);
    fireEvent.click(header);
    expect(container.querySelector(".nice-interval")).not.toBeNull();
  });
});
