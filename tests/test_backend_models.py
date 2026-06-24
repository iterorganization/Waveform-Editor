"""Tests for backend Pydantic models."""
import pytest
from backend.models import (
    CoilPath,
    CoilRect,
    ContourSegment,
    EvaluateRequest,
    EvaluateResponse,
    LoadGeometriesRequest,
    MachineGeometriesResponse,
    NiceRunConfig,
    ParsedConfig,
    SettingsData,
    TimestepResult,
    WallPath,
    WaveformInfo,
    WaveformValues,
)


class TestWaveformInfo:
    def test_required_fields(self):
        wf = WaveformInfo(name="kappa", group_path=["NICE Shape"])
        assert wf.name == "kappa"
        assert wf.group_path == ["NICE Shape"]
        assert wf.is_derived is False

    def test_derived(self):
        wf = WaveformInfo(name="derived", group_path=[], is_derived=True)
        assert wf.is_derived is True

    def test_nested_group_path(self):
        wf = WaveformInfo(name="w", group_path=["outer", "inner"])
        assert len(wf.group_path) == 2


class TestParsedConfig:
    def test_defaults(self):
        pc = ParsedConfig()
        assert pc.waveforms == []
        assert pc.time_start == 0.0
        assert pc.time_end == 100.0
        assert pc.yaml_content == ""
        assert pc.load_error == ""

    def test_with_waveforms(self):
        pc = ParsedConfig(
            waveforms=[WaveformInfo(name="w", group_path=[])],
            time_start=5.0,
            time_end=50.0,
        )
        assert len(pc.waveforms) == 1
        assert pc.time_start == 5.0
        assert pc.time_end == 50.0

    def test_load_error_propagated(self):
        pc = ParsedConfig(load_error="YAML parse error at line 3")
        assert pc.load_error == "YAML parse error at line 3"


class TestEvaluateRequest:
    def test_basic(self):
        req = EvaluateRequest(yaml_content="content", time_points=[0.0, 1.0, 2.0])
        assert req.yaml_content == "content"
        assert req.time_points == [0.0, 1.0, 2.0]
        assert req.waveform_names is None

    def test_with_filter(self):
        req = EvaluateRequest(
            yaml_content="y", time_points=[0.0], waveform_names=["kappa", "delta"]
        )
        assert req.waveform_names == ["kappa", "delta"]


class TestEvaluateResponse:
    def test_defaults(self):
        r = EvaluateResponse()
        assert r.waveforms == []
        assert r.error == ""

    def test_with_waveform(self):
        r = EvaluateResponse(waveforms=[WaveformValues(name="w", times=[0.0], values=[5.0])])
        assert len(r.waveforms) == 1
        assert r.waveforms[0].name == "w"
        assert r.waveforms[0].values == [5.0]

    def test_error_field(self):
        r = EvaluateResponse(error="something went wrong")
        assert r.error == "something went wrong"


class TestTimestepResult:
    def test_required_fields(self):
        r = TimestepResult(t=5.0, index=0, total=10)
        assert r.t == 5.0
        assert r.index == 0
        assert r.total == 10
        assert r.status == "success"

    def test_default_lists_empty(self):
        r = TimestepResult(t=0.0, index=0, total=1)
        assert r.contours == []
        assert r.separatrix_r == []
        assert r.separatrix_z == []
        assert r.o_points == []
        assert r.x_points == []
        assert r.metrics == {}
        assert r.coil_names == []
        assert r.coil_currents == []

    def test_with_metrics(self):
        r = TimestepResult(
            t=10.0, index=1, total=5,
            metrics={"elongation": 1.8, "triangularity": 0.43},
        )
        assert r.metrics["elongation"] == 1.8
        assert r.metrics["triangularity"] == 0.43

    def test_with_coils(self):
        r = TimestepResult(
            t=0.0, index=0, total=1,
            coil_names=["PF1", "PF2"],
            coil_currents=[1e6, -5e5],
        )
        assert r.coil_names == ["PF1", "PF2"]
        assert r.coil_currents[0] == pytest.approx(1e6)

    def test_error_status(self):
        r = TimestepResult(t=0.0, index=0, total=1, status="error", error="NICE crashed")
        assert r.status == "error"
        assert r.error == "NICE crashed"

    def test_input_profiles(self):
        r = TimestepResult(
            t=0.0, index=0, total=1,
            input_psi_norm=[0.0, 0.5, 1.0],
            input_dpressure_dpsi=[1.0, 0.5, 0.0],
            input_f_df_dpsi=[2.0, 1.5, 1.0],
        )
        assert r.input_psi_norm == [0.0, 0.5, 1.0]
        assert len(r.input_dpressure_dpsi) == 3


class TestSettingsData:
    def test_defaults(self):
        s = SettingsData()
        assert s.nice_inv_executable == "nice_imas_inv_muscle3"
        assert s.nice_dir_executable == "nice_imas_dir_muscle3"
        assert s.nice_mode == "NICE Inverse"
        assert s.machine_preset == "Custom"
        assert s.md_pf_active == ""
        assert s.md_pf_passive == ""
        assert s.md_wall == ""
        assert s.md_iron_core == ""
        assert s.verbose == 1
        assert s.environment == {}

    def test_custom_values(self):
        s = SettingsData(
            nice_inv_executable="my_nice",
            nice_mode="NICE Direct",
            verbose=2,
            environment={"OMP_NUM_THREADS": "4"},
        )
        assert s.nice_inv_executable == "my_nice"
        assert s.nice_mode == "NICE Direct"
        assert s.verbose == 2
        assert s.environment["OMP_NUM_THREADS"] == "4"


class TestNiceRunConfig:
    def test_defaults(self):
        cfg = NiceRunConfig(yaml_content="yaml", timesteps=[0.0, 10.0, 20.0])
        assert cfg.n_bnd_points == 96
        assert cfg.nice_mode == "NICE Inverse"
        assert cfg.environment == {}
        assert cfg.verbose == 1

    def test_custom(self):
        cfg = NiceRunConfig(
            yaml_content="y",
            timesteps=[5.0],
            n_bnd_points=128,
            environment={"MY_VAR": "val"},
            verbose=2,
        )
        assert cfg.n_bnd_points == 128
        assert cfg.environment["MY_VAR"] == "val"
        assert cfg.verbose == 2

    def test_timesteps_preserved(self):
        ts = [0.0, 10.0, 20.0, 30.0]
        cfg = NiceRunConfig(yaml_content="y", timesteps=ts)
        assert cfg.timesteps == ts


class TestGeometryModels:
    def test_coil_rect(self):
        r = CoilRect(r0=5.0, z0=-0.5, r1=5.5, z1=0.5, name="PF1")
        assert r.r0 == 5.0
        assert r.r1 == 5.5
        assert r.name == "PF1"

    def test_coil_path(self):
        p = CoilPath(r=[5.0, 5.5, 5.5, 5.0], z=[-0.5, -0.5, 0.5, 0.5], name="CS1")
        assert len(p.r) == 4
        assert p.name == "CS1"

    def test_wall_path(self):
        w = WallPath(r=[4.0, 8.0, 8.0, 4.0], z=[-5.0, -5.0, 5.0, 5.0], name="wall")
        assert w.name == "wall"

    def test_contour_segment(self):
        c = ContourSegment(x=[5.0, 6.0, 7.0], y=[-1.0, 0.0, -1.0], psi=0.5)
        assert c.psi == 0.5
        assert len(c.x) == 3


class TestMachineGeometriesResponse:
    def test_defaults(self):
        r = MachineGeometriesResponse()
        assert r.coil_rectangles == []
        assert r.coil_paths == []
        assert r.wall_limiter == []
        assert r.vacuum_vessel == []
        assert r.error == ""

    def test_with_coil_rect(self):
        r = MachineGeometriesResponse(
            coil_rectangles=[CoilRect(r0=5.0, z0=-0.5, r1=5.5, z1=0.5, name="PF1")]
        )
        assert len(r.coil_rectangles) == 1

    def test_mixed_geometry(self):
        r = MachineGeometriesResponse(
            coil_rectangles=[CoilRect(r0=1.0, z0=-1.0, r1=2.0, z1=1.0, name="PF1")],
            coil_paths=[CoilPath(r=[3.0, 4.0], z=[0.0, 0.0], name="CS1")],
            wall_limiter=[WallPath(r=[1.0, 9.0], z=[-8.0, 8.0], name="wall")],
        )
        assert len(r.coil_rectangles) == 1
        assert len(r.coil_paths) == 1
        assert len(r.wall_limiter) == 1
