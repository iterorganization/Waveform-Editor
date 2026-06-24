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
