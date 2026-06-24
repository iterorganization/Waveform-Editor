import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PlaybackScrubber } from "../../components/visualization/PlaybackScrubber";
import { useStore } from "../../store";
import type { TimestepResult } from "../../types";

function makeResult(t: number, index: number, total: number): TimestepResult {
  return {
    t, index, total, status: "success",
    contours: [], separatrix_r: [], separatrix_z: [],
    o_points: [], x_points: [], metrics: {},
    psi_norm: [], dpressure_dpsi: [], f_df_dpsi: [],
    input_psi_norm: [], input_dpressure_dpsi: [], input_f_df_dpsi: [],
    coil_names: [], coil_currents: [], input_values: {},
  };
}

const RESULTS = [
  makeResult(0, 0, 3),
  makeResult(10, 1, 3),
  makeResult(20, 2, 3),
];

beforeEach(() => {
  useStore.setState({
    results: [],
    currentResultIndex: 0,
    isPlaying: false,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});


describe("PlaybackScrubber — hidden when empty", () => {
  it("renders nothing when there are no results", () => {
    const { container } = render(<PlaybackScrubber />);
    expect(container.firstChild).toBeNull();
  });
});


describe("PlaybackScrubber — with results", () => {
  beforeEach(() => {
    useStore.setState({ results: RESULTS, currentResultIndex: 0, isPlaying: false });
  });

  it("renders when results exist", () => {
    render(<PlaybackScrubber />);
    expect(screen.getByRole("slider")).toBeInTheDocument();
  });

  it("shows time display", () => {
    render(<PlaybackScrubber />);
    expect(screen.getByText("t = 0.00 s")).toBeInTheDocument();
  });

  it("shows index / total counter", () => {
    render(<PlaybackScrubber />);
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
  });

  it("shows play button when not playing", () => {
    render(<PlaybackScrubber />);
    expect(screen.getByText("▶")).toBeInTheDocument();
  });

  it("shows pause button when playing", () => {
    useStore.setState({ results: RESULTS, currentResultIndex: 0, isPlaying: true });
    render(<PlaybackScrubber />);
    expect(screen.getByText("⏸")).toBeInTheDocument();
  });
});


describe("PlaybackScrubber — navigation", () => {
  beforeEach(() => {
    useStore.setState({ results: RESULTS, currentResultIndex: 1, isPlaying: false });
  });

  it("previous button decrements index", () => {
    render(<PlaybackScrubber />);
    fireEvent.click(screen.getByText("⏮"));
    expect(useStore.getState().currentResultIndex).toBe(0);
  });

  it("next button increments index", () => {
    render(<PlaybackScrubber />);
    fireEvent.click(screen.getByText("⏭"));
    expect(useStore.getState().currentResultIndex).toBe(2);
  });

  it("previous button is disabled at index 0", () => {
    useStore.setState({ results: RESULTS, currentResultIndex: 0 });
    render(<PlaybackScrubber />);
    expect(screen.getByText("⏮").closest("button")).toBeDisabled();
  });

  it("next button is disabled at last index", () => {
    useStore.setState({ results: RESULTS, currentResultIndex: 2 });
    render(<PlaybackScrubber />);
    expect(screen.getByText("⏭").closest("button")).toBeDisabled();
  });

  it("slider updates index on change", () => {
    render(<PlaybackScrubber />);
    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "2" } });
    expect(useStore.getState().currentResultIndex).toBe(2);
  });

  it("slider max equals results.length - 1", () => {
    render(<PlaybackScrubber />);
    const slider = screen.getByRole("slider");
    expect(slider.getAttribute("max")).toBe("2");
  });
});


describe("PlaybackScrubber — play/pause", () => {
  it("play button calls setIsPlaying(true)", () => {
    const setIsPlaying = vi.spyOn(useStore.getState(), "setIsPlaying");
    useStore.setState({ results: RESULTS, currentResultIndex: 0, isPlaying: false });
    render(<PlaybackScrubber />);
    fireEvent.click(screen.getByText("▶"));
    expect(setIsPlaying).toHaveBeenCalledWith(true);
  });

  it("pause button calls setIsPlaying(false)", () => {
    const setIsPlaying = vi.spyOn(useStore.getState(), "setIsPlaying");
    useStore.setState({ results: RESULTS, currentResultIndex: 0, isPlaying: true });
    render(<PlaybackScrubber />);
    fireEvent.click(screen.getByText("⏸"));
    expect(setIsPlaying).toHaveBeenCalledWith(false);
  });
});
