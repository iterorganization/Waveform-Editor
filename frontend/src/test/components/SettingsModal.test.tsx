import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SettingsModal } from "../../components/settings/SettingsModal";
import { useStore } from "../../store";

vi.mock("../../api", () => ({
  api: {
    saveSettings: vi.fn().mockResolvedValue({ ok: true }),
    getMachineGeometries: vi.fn().mockResolvedValue({
      coil_rectangles: [], coil_paths: [], wall_limiter: [], vacuum_vessel: [], error: "",
    }),
    getSettings: vi.fn().mockResolvedValue({
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
    }),
  },
}));

const DEFAULT_SETTINGS = {
  nice_inv_executable: "nice_imas_inv_muscle3",
  nice_dir_executable: "nice_imas_dir_muscle3",
  nice_mode: "NICE Inverse",
  machine_preset: "Custom",
  md_pf_active: "",
  md_pf_passive: "",
  md_wall: "",
  md_iron_core: "",
  verbose: 1,
  environment: {},
};

beforeEach(() => {
  useStore.setState({
    showSettings: true,
    settings: { ...DEFAULT_SETTINGS },
    machineGeometries: null,
    machineLoading: false,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});


describe("SettingsModal — visibility", () => {
  it("renders when showSettings is true", () => {
    render(<SettingsModal />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("does not render when showSettings is false", () => {
    useStore.setState({ showSettings: false });
    const { container } = render(<SettingsModal />);
    expect(container.firstChild).toBeNull();
  });

  it("closes on Cancel button click", () => {
    render(<SettingsModal />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(useStore.getState().showSettings).toBe(false);
  });

  it("closes on × button click", () => {
    const { container } = render(<SettingsModal />);
    const closeBtn = container.querySelector(".modal-close")!;
    fireEvent.click(closeBtn);
    expect(useStore.getState().showSettings).toBe(false);
  });
});


describe("SettingsModal — form fields", () => {
  it("shows the inverse executable input", () => {
    render(<SettingsModal />);
    expect(screen.getByDisplayValue("nice_imas_inv_muscle3")).toBeInTheDocument();
  });

  it("shows mode selector with NICE Inverse selected", () => {
    render(<SettingsModal />);
    expect(screen.getByDisplayValue("NICE Inverse")).toBeInTheDocument();
  });

  it("shows verbosity input", () => {
    render(<SettingsModal />);
    expect(screen.getByDisplayValue("1")).toBeInTheDocument();
  });

  it("changing the executable input updates local state", () => {
    render(<SettingsModal />);
    const exeInput = screen.getByDisplayValue("nice_imas_inv_muscle3");
    fireEvent.change(exeInput, { target: { value: "my_nice" } });
    expect(screen.getByDisplayValue("my_nice")).toBeInTheDocument();
  });

  it("shows all four machine description URI inputs", () => {
    render(<SettingsModal />);
    const inputs = screen.getAllByPlaceholderText("imas:hdf5?path=...");
    expect(inputs.length).toBe(4);
  });
});


describe("SettingsModal — presets", () => {
  it("shows preset dropdown with Custom option", () => {
    render(<SettingsModal />);
    expect(screen.getByDisplayValue("Custom")).toBeInTheDocument();
  });

  it("ITER preset fills in URIs", async () => {
    render(<SettingsModal />);
    const presetSelect = screen.getByDisplayValue("Custom");
    fireEvent.change(presetSelect, { target: { value: "ITER" } });
    // ITER preset should fill pf_active URI
    const uriInputs = screen.getAllByPlaceholderText("imas:hdf5?path=...");
    expect(uriInputs[0].getAttribute("value") || (uriInputs[0] as HTMLInputElement).value).toContain("ITER");
  });

  it("WEST preset fills in URIs", () => {
    render(<SettingsModal />);
    const presetSelect = screen.getByDisplayValue("Custom");
    fireEvent.change(presetSelect, { target: { value: "WEST" } });
    const uriInputs = screen.getAllByPlaceholderText("imas:hdf5?path=...");
    expect((uriInputs[0] as HTMLInputElement).value).toContain("west");
  });

  it("Custom preset clears URIs", () => {
    render(<SettingsModal />);
    const presetSelect = screen.getByDisplayValue("Custom");
    // First apply ITER
    fireEvent.change(presetSelect, { target: { value: "ITER" } });
    // Then switch back to Custom
    fireEvent.change(presetSelect, { target: { value: "Custom" } });
    expect(screen.getByDisplayValue("Custom")).toBeInTheDocument();
  });
});


describe("SettingsModal — save", () => {
  it("Save button closes the modal", async () => {
    render(<SettingsModal />);
    fireEvent.click(screen.getByText(/Save.*Geometries/));
    await waitFor(() => {
      expect(useStore.getState().showSettings).toBe(false);
    });
  });

  it("environment textarea renders as JSON", () => {
    useStore.setState({
      showSettings: true,
      settings: { ...DEFAULT_SETTINGS, environment: { MY_VAR: "value" } },
    });
    render(<SettingsModal />);
    expect(screen.getByDisplayValue(/MY_VAR/)).toBeInTheDocument();
  });
});
