"""Pydantic models for the Waveform Editor API."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class WaveformInfo(BaseModel):
    name: str
    group_path: list[str]
    is_derived: bool = False


class ParsedConfig(BaseModel):
    waveforms: list[WaveformInfo] = []
    time_start: float = 0.0
    time_end: float = 100.0
    yaml_content: str = ""
    load_error: str = ""
    annotations: list[str] = []  # formatted "Line N: message" strings from waveform validation


class EvaluateRequest(BaseModel):
    yaml_content: str
    time_points: list[float]
    waveform_names: Optional[list[str]] = None


class WaveformValues(BaseModel):
    name: str
    times: list[float]
    values: list[float]


class EvaluateResponse(BaseModel):
    waveforms: list[WaveformValues] = []
    error: str = ""


class LoadGeometriesRequest(BaseModel):
    md_pf_active_uri: str = ""
    md_wall_uri: str = ""


class CoilRect(BaseModel):
    r0: float
    z0: float
    r1: float
    z1: float
    name: str


class CoilPath(BaseModel):
    r: list[float]
    z: list[float]
    name: str


class WallPath(BaseModel):
    r: list[float]
    z: list[float]
    name: str


class MachineGeometriesResponse(BaseModel):
    coil_rectangles: list[CoilRect] = []
    coil_paths: list[CoilPath] = []
    wall_limiter: list[WallPath] = []
    vacuum_vessel: list[WallPath] = []
    error: str = ""


class NiceRunConfig(BaseModel):
    yaml_content: str
    timesteps: list[float]
    n_bnd_points: int = 96
    nice_mode: str = "NICE Inverse"
    inv_executable: str = "nice_imas_inv_muscle3"
    dir_executable: str = "nice_imas_dir_muscle3"
    environment: dict[str, str] = Field(default_factory=dict)
    md_pf_active_uri: str = ""
    md_pf_passive_uri: str = ""
    md_wall_uri: str = ""
    md_iron_core_uri: str = ""
    verbose: int = 1
    # Use the previous timestep's converged equilibrium as the initial guess
    # for the next one (falls back to cold start after a failed timestep)
    warm_start: bool = True
    # "params": desired boundary from the Miller-like shape waveforms;
    # "gaps": desired boundary from gap waveforms + gap_definitions
    shape_mode: str = "params"
    gap_definitions: list[GapDefinition] = Field(default_factory=list)
    # Number of parallel NICE instances (0 = auto: all available cores).
    # Parallel runs disable warm start, which is sequential by nature.
    parallel_workers: int = 1


class ContourSegment(BaseModel):
    x: list[float]
    y: list[float]
    psi: float


class TimestepResult(BaseModel):
    t: float
    index: int
    total: int
    status: str = "success"  # "success" | "error" | "running"
    error: Optional[str] = None
    contours: list[ContourSegment] = []
    separatrix_r: list[float] = []
    separatrix_z: list[float] = []
    o_points: list[dict] = []
    x_points: list[dict] = []
    metrics: dict[str, float] = Field(default_factory=dict)
    # Output profiles from NICE
    psi_norm: list[float] = []
    dpressure_dpsi: list[float] = []
    f_df_dpsi: list[float] = []
    # Input profiles (prescribed)
    input_psi_norm: list[float] = []
    input_dpressure_dpsi: list[float] = []
    input_f_df_dpsi: list[float] = []
    coil_names: list[str] = []
    coil_currents: list[float] = []
    input_values: dict[str, float] = Field(default_factory=dict)


class TendencyInfo(BaseModel):
    index: int
    type: str
    line_number: int
    start_time: float
    end_time: float
    params: dict[str, float] = Field(default_factory=dict)
    piecewise_times: list[float] = Field(default_factory=list)
    piecewise_values: list[float] = Field(default_factory=list)
    inner_tendencies: list['TendencyInfo'] = Field(default_factory=list)


class TendenciesRequest(BaseModel):
    yaml_content: str
    waveform_name: str


class TendenciesResponse(BaseModel):
    tendencies: list[TendencyInfo] = []
    error: str = ""


class TendenciesBatchRequest(BaseModel):
    yaml_content: str
    waveform_names: list[str] = Field(default_factory=list)


class SyncTendencies(BaseModel):
    tendencies: dict[str, list[TendencyInfo]] = Field(default_factory=dict)
    tendency_errors: dict[str, str] = Field(default_factory=dict)


class SyncRequest(BaseModel):
    """One-round-trip request for everything the UI needs after a YAML edit."""
    yaml_content: str
    min_points: int = 200
    max_points: int = 2000
    tendency_names: list[str] = Field(default_factory=list)


class SyncResponse(SyncTendencies):
    parsed: ParsedConfig
    # Preview evaluation of every waveform on one shared time grid
    # (non-finite values are sent as null — NaN is not valid JSON)
    times: list[float] = Field(default_factory=list)
    values: dict[str, list[float | None]] = Field(default_factory=dict)


class GapDefinition(BaseModel):
    name: str
    r: float
    z: float
    angle: float
    value: float


class LoadGapsRequest(BaseModel):
    uri: str
    time: float = 0.0


class GapsResponse(BaseModel):
    gaps: list[GapDefinition] = []
    error: str = ""


class ShapeOutlineRequest(BaseModel):
    yaml_content: str
    time: float
    mode: str = "params"   # "params" or "gaps"
    gap_waveform_names: list[str] = []  # waveform names for each gap (gap mode)
    gap_definitions: list[GapDefinition] = []  # reference r,z,angle for each gap


class ShapeOutlineResponse(BaseModel):
    outline_r: list[float] = []
    outline_z: list[float] = []
    param_values: dict[str, float] = {}
    error: str = ""


class InverseMillerRequest(BaseModel):
    current_params: dict[str, float]  # kappa, delta, a, center_r, center_z, rx, zx
    drag_r: float   # moved point new R position
    drag_z: float   # moved point new Z position
    theta: float    # Miller angle parameter at which the drag occurred


class InverseMillerResponse(BaseModel):
    new_params: dict[str, float] = {}
    error: str = ""


class SettingsData(BaseModel):
    nice_inv_executable: str = "nice_imas_inv_muscle3"
    nice_dir_executable: str = "nice_imas_dir_muscle3"
    nice_mode: str = "NICE Inverse"
    machine_preset: str = "Custom"
    md_pf_active: str = ""
    md_pf_passive: str = ""
    md_wall: str = ""
    md_iron_core: str = ""
    verbose: int = 1
    environment: dict[str, str] = Field(default_factory=dict)
