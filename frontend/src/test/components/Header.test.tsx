import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Header } from "../../components/Header";
import { useStore } from "../../store";

vi.mock("../../api", () => ({
  api: {
    parseYaml: vi.fn().mockResolvedValue({ waveforms: [], time_start: 0, time_end: 100, yaml_content: "", load_error: "" }),
    saveSettings: vi.fn().mockResolvedValue({ ok: true }),
  },
}));

// Suppress URL.createObjectURL which is not available in jsdom
beforeAll(() => {
  global.URL.createObjectURL = vi.fn(() => "blob:fake");
  global.URL.revokeObjectURL = vi.fn();
});

beforeEach(() => {
  useStore.setState({
    yamlContent: "some: yaml",
    niceRunning: false,
    niceProgress: { current: 0, total: 0 },
    niceStatus: "",
    showAdvancedEditor: false,
    showSettings: false,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});


describe("Header — branding", () => {
  it("renders the brand name", () => {
    render(<Header />);
    expect(screen.getByText("Waveform Editor")).toBeInTheDocument();
  });
});


describe("Header — NICE run state", () => {
  it("shows Run NICE button when not running", () => {
    render(<Header />);
    expect(screen.getByText(/Run NICE/)).toBeInTheDocument();
  });

  it("shows Stop button when NICE is running", () => {
    useStore.setState({ niceRunning: true, niceStatus: "Running...", niceProgress: { current: 2, total: 5 } });
    render(<Header />);
    expect(screen.getByText(/Stop/)).toBeInTheDocument();
  });

  it("shows progress percentage when running", () => {
    useStore.setState({ niceRunning: true, niceStatus: "Running...", niceProgress: { current: 2, total: 4 } });
    render(<Header />);
    expect(screen.getByText(/50%/)).toBeInTheDocument();
  });

  it("shows niceStatus text when not running but status is set", () => {
    useStore.setState({ niceStatus: "Done — 10 timesteps completed" });
    render(<Header />);
    expect(screen.getByText(/Done/)).toBeInTheDocument();
  });

  it("Stop button calls stopNice", () => {
    const stopNice = vi.spyOn(useStore.getState(), "stopNice");
    useStore.setState({ niceRunning: true, niceStatus: "Running", niceProgress: { current: 0, total: 1 } });
    render(<Header />);
    fireEvent.click(screen.getByText(/Stop/));
    expect(stopNice).toHaveBeenCalled();
  });
});


describe("Header — settings", () => {
  it("renders the Settings button", () => {
    render(<Header />);
    expect(screen.getByTitle("Settings")).toBeInTheDocument();
  });

  it("clicking Settings opens the settings modal", () => {
    render(<Header />);
    fireEvent.click(screen.getByTitle("Settings"));
    expect(useStore.getState().showSettings).toBe(true);
  });
});


describe("Header — advanced editor toggle", () => {
  it("shows Advanced button when editor is hidden", () => {
    render(<Header />);
    expect(screen.getByText(/Advanced/)).toBeInTheDocument();
  });

  it("shows YAML button when editor is visible", () => {
    useStore.setState({ showAdvancedEditor: true });
    render(<Header />);
    expect(screen.getByText(/YAML/)).toBeInTheDocument();
  });

  it("clicking Advanced toggles showAdvancedEditor", () => {
    render(<Header />);
    fireEvent.click(screen.getByText(/Advanced/));
    expect(useStore.getState().showAdvancedEditor).toBe(true);
  });
});


describe("Header — file buttons", () => {
  it("renders Open button", () => {
    render(<Header />);
    expect(screen.getByText(/Open/)).toBeInTheDocument();
  });

  it("renders Save button", () => {
    render(<Header />);
    expect(screen.getByText(/Save/)).toBeInTheDocument();
  });
});
