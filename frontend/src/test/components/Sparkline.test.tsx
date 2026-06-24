import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sparkline } from "../../components/timeline/Sparkline";

describe("Sparkline — empty data", () => {
  it("renders a dashed placeholder line when no data", () => {
    const { container } = render(<Sparkline times={[]} values={[]} />);
    const svg = container.querySelector("svg.sparkline-svg");
    expect(svg).not.toBeNull();
    const line = svg!.querySelector("line");
    expect(line).not.toBeNull();
    expect(line!.getAttribute("stroke-dasharray")).toBeTruthy();
  });

  it("renders SVG with correct default dimensions", () => {
    const { container } = render(<Sparkline times={[]} values={[]} />);
    const svg = container.querySelector("svg");
    expect(svg!.getAttribute("width")).toBe("80");
    expect(svg!.getAttribute("height")).toBe("22");
  });

  it("renders SVG with custom dimensions", () => {
    const { container } = render(<Sparkline times={[]} values={[]} width={120} height={30} />);
    const svg = container.querySelector("svg");
    expect(svg!.getAttribute("width")).toBe("120");
    expect(svg!.getAttribute("height")).toBe("30");
  });
});


describe("Sparkline — with data", () => {
  const times = [0, 25, 50, 75, 100];
  const values = [1, 2, 3, 2, 1];

  it("renders a polyline when data is provided", () => {
    const { container } = render(<Sparkline times={times} values={values} />);
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
  });

  it("does not render a placeholder dashed line when data exists", () => {
    const { container } = render(<Sparkline times={times} values={values} />);
    const line = container.querySelector("line");
    expect(line).toBeNull();
  });

  it("polyline has correct number of points (space-separated pairs)", () => {
    const { container } = render(<Sparkline times={times} values={values} />);
    const polyline = container.querySelector("polyline")!;
    const pts = polyline.getAttribute("points")!.trim().split(" ");
    expect(pts).toHaveLength(times.length);
  });

  it("applies the color prop to the polyline stroke", () => {
    const { container } = render(<Sparkline times={times} values={values} color="#ff0000" />);
    const polyline = container.querySelector("polyline")!;
    expect(polyline.getAttribute("stroke")).toBe("#ff0000");
  });

  it("renders correctly with a single data point (no range)", () => {
    const { container } = render(<Sparkline times={[50]} values={[3.0]} />);
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
    const pts = polyline!.getAttribute("points")!.trim().split(" ");
    expect(pts).toHaveLength(1);
  });

  it("renders correctly with identical values (flat line)", () => {
    const { container } = render(
      <Sparkline times={[0, 50, 100]} values={[5, 5, 5]} />
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
  });
});
