import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ComparisonPanel } from "../../components/comparison/ComparisonPanel";
import { useStore } from "../../store";

beforeEach(() => {
  useStore.setState({
    activeComparisonTab: 0,
    results: [],
    currentResultIndex: 0,
  });
});


describe("ComparisonPanel — tabs", () => {
  it("renders all four tabs", () => {
    render(<ComparisonPanel />);
    expect(screen.getByText("Shape metrics")).toBeInTheDocument();
    expect(screen.getByText("Ip vs time")).toBeInTheDocument();
    expect(screen.getByText("Profiles")).toBeInTheDocument();
    expect(screen.getByText("Coil currents")).toBeInTheDocument();
  });

  it("first tab is active by default", () => {
    render(<ComparisonPanel />);
    const shapeTab = screen.getByText("Shape metrics").closest("button")!;
    expect(shapeTab.className).toContain("active");
  });

  it("clicking Ip vs time activates that tab", () => {
    render(<ComparisonPanel />);
    fireEvent.click(screen.getByText("Ip vs time"));
    expect(useStore.getState().activeComparisonTab).toBe(1);
  });

  it("clicking Profiles activates tab 2", () => {
    render(<ComparisonPanel />);
    fireEvent.click(screen.getByText("Profiles"));
    expect(useStore.getState().activeComparisonTab).toBe(2);
  });

  it("clicking Coil currents activates tab 3", () => {
    render(<ComparisonPanel />);
    fireEvent.click(screen.getByText("Coil currents"));
    expect(useStore.getState().activeComparisonTab).toBe(3);
  });

  it("active tab button has active class", () => {
    useStore.setState({ activeComparisonTab: 2 });
    render(<ComparisonPanel />);
    const profilesTab = screen.getByText("Profiles").closest("button")!;
    expect(profilesTab.className).toContain("active");
  });

  it("inactive tabs do not have active class", () => {
    useStore.setState({ activeComparisonTab: 0 });
    render(<ComparisonPanel />);
    const ipTab = screen.getByText("Ip vs time").closest("button")!;
    expect(ipTab.className).not.toContain("active");
  });
});


describe("ComparisonPanel — content area", () => {
  it("renders a content area for the active tab", () => {
    const { container } = render(<ComparisonPanel />);
    expect(container.querySelector(".comp-body")).not.toBeNull();
  });

  it("renders content area for Ip tab", () => {
    useStore.setState({ activeComparisonTab: 1 });
    const { container } = render(<ComparisonPanel />);
    expect(container.querySelector(".comp-body")).not.toBeNull();
  });

  it("shows placeholder text when on Profiles tab with no results", () => {
    useStore.setState({ activeComparisonTab: 2 });
    render(<ComparisonPanel />);
    expect(screen.getByText(/Run NICE/)).toBeInTheDocument();
  });

  it("shows placeholder text when on Coil currents tab with no results", () => {
    useStore.setState({ activeComparisonTab: 3 });
    render(<ComparisonPanel />);
    expect(screen.getByText(/Run NICE/)).toBeInTheDocument();
  });
});
