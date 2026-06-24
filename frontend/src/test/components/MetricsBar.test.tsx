import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricsBar } from "../../components/visualization/MetricsBar";
import { useStore } from "../../store";
import type { TimestepResult } from "../../types";

function makeResult(metrics: Record<string, number>): TimestepResult {
  return {
    t: 10.0, index: 0, total: 1, status: "success",
    contours: [], separatrix_r: [], separatrix_z: [],
    o_points: [], x_points: [], metrics,
    psi_norm: [], dpressure_dpsi: [], f_df_dpsi: [],
    input_psi_norm: [], input_dpressure_dpsi: [], input_f_df_dpsi: [],
    coil_names: [], coil_currents: [], input_values: {},
  };
}

beforeEach(() => {
  useStore.setState({ results: [], currentResultIndex: 0 });
});


describe("MetricsBar — no results", () => {
  it("renders all 9 metric chips", () => {
    render(<MetricsBar />);
    const chips = document.querySelectorAll(".metric-chip");
    expect(chips.length).toBe(9);
  });

  it("shows dash for every metric when no results", () => {
    render(<MetricsBar />);
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBe(9);
  });

  it("renders κ symbol", () => {
    render(<MetricsBar />);
    expect(screen.getByText("κ")).toBeInTheDocument();
  });

  it("renders Ip symbol", () => {
    render(<MetricsBar />);
    expect(screen.getByText("Ip")).toBeInTheDocument();
  });
});


describe("MetricsBar — with results", () => {
  it("shows elongation value when result present", () => {
    useStore.setState({
      results: [makeResult({ elongation: 1.800 })],
      currentResultIndex: 0,
    });
    render(<MetricsBar />);
    expect(screen.getByText("1.800")).toBeInTheDocument();
  });

  it("formats Ip in MA", () => {
    useStore.setState({
      results: [makeResult({ ip_actual: -15_000_000 })],
      currentResultIndex: 0,
    });
    render(<MetricsBar />);
    expect(screen.getByText("-15.00 MA")).toBeInTheDocument();
  });

  it("shows — for missing metrics while showing present ones", () => {
    useStore.setState({
      results: [makeResult({ elongation: 1.8 })],
      currentResultIndex: 0,
    });
    render(<MetricsBar />);
    expect(screen.getByText("1.800")).toBeInTheDocument();
    // Other metrics should still show dash
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBe(8); // 8 missing metrics
  });

  it("updates when currentResultIndex changes", () => {
    useStore.setState({
      results: [
        makeResult({ elongation: 1.8 }),
        makeResult({ elongation: 2.0 }),
      ],
      currentResultIndex: 0,
    });
    const { rerender } = render(<MetricsBar />);
    expect(screen.getByText("1.800")).toBeInTheDocument();

    useStore.setState({ currentResultIndex: 1 });
    rerender(<MetricsBar />);
    expect(screen.getByText("2.000")).toBeInTheDocument();
  });

  it("formats minor radius with unit m", () => {
    useStore.setState({
      results: [makeResult({ minor_radius: 2.000 })],
      currentResultIndex: 0,
    });
    render(<MetricsBar />);
    expect(screen.getByText("2.000 m")).toBeInTheDocument();
  });

  it("shows triangularity without unit suffix", () => {
    useStore.setState({
      results: [makeResult({ triangularity: 0.430 })],
      currentResultIndex: 0,
    });
    render(<MetricsBar />);
    expect(screen.getByText("0.430")).toBeInTheDocument();
  });
});
