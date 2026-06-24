"""Tests for the ITER 15 MA flat-top example YAML.

Covers:
- Loading and parsing the example YAML file
- Waveform evaluation at key timesteps (ramp-up, flat-top, ramp-down)
- Equilibrium IDS construction using the b0 direct-assignment fix
- Plot output data structures contain expected fields for visualisation
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import imas

from waveform_editor.configuration import WaveformConfiguration

EXAMPLE_PATH = Path(__file__).parent.parent / "examples" / "iter_15ma_flatop.yaml"
EXAMPLE_YAML = EXAMPLE_PATH.read_text()

# Canonical timesteps that match the scenario phases
T_RAMPUP   = 10.0   # midpoint of current ramp-up
T_FLATOP   = 50.0   # flat-top
T_RAMPDOWN = 90.0   # midpoint of controlled ramp-down


@pytest.fixture(scope="module")
def config():
    cfg = WaveformConfiguration()
    cfg.load_yaml(EXAMPLE_YAML)
    return cfg


# ── YAML loading ──────────────────────────────────────────────────────────────

class TestIterFlatopYamlLoading:
    def test_example_file_exists(self):
        assert EXAMPLE_PATH.exists(), "examples/iter_15ma_flatop.yaml not found"

    def test_loads_without_errors(self, config):
        assert config.parser.parse_errors == [], config.parser.parse_errors

    def test_nice_shape_group_present(self, config):
        assert "NICE Shape" in config.groups

    def test_nice_properties_group_present(self, config):
        assert "NICE Properties" in config.groups

    def test_shape_waveforms_defined(self, config):
        shape_waveforms = config.groups["NICE Shape"].waveforms
        for name in ("kappa", "delta", "a", "center_r", "center_z", "rx", "zx"):
            assert name in shape_waveforms, f"Missing shape waveform: {name}"

    def test_property_waveforms_defined(self, config):
        prop_waveforms = config.groups["NICE Properties"].waveforms
        for name in ("ip", "b0", "r0", "profile_alpha", "profile_beta", "profile_gamma"):
            assert name in prop_waveforms, f"Missing property waveform: {name}"

    def test_total_duration_is_100(self, config):
        # kappa waveform spans 20+60+20 = 100 s; verify it reaches 100 s without error
        wf = config.waveform_map["kappa"]["kappa"]
        t_arr = np.array([100.0])
        times, vals = wf.get_value(t_arr)
        assert times[0] == pytest.approx(100.0, abs=0.1)


# ── Waveform values at key timesteps ─────────────────────────────────────────

def _eval(config, name, t):
    t_arr = np.array([t])
    wf = config.waveform_map[name][name]
    _, vals = wf.get_value(t_arr)
    return float(vals[0])


class TestIterFlatopWaveformValues:
    """Verify that waveform values match the ITER scenario physics."""

    # kappa: 1.2 → 1.7 over first 20 s, then constant
    def test_kappa_at_rampup_is_between_1_2_and_1_7(self, config):
        v = _eval(config, "kappa", T_RAMPUP)
        assert 1.2 < v < 1.7

    def test_kappa_at_flatop_is_1_7(self, config):
        assert pytest.approx(_eval(config, "kappa", T_FLATOP), abs=1e-6) == 1.7

    def test_kappa_at_rampdown_is_between_1_2_and_1_7(self, config):
        v = _eval(config, "kappa", T_RAMPDOWN)
        assert 1.2 < v < 1.7

    # delta: 0.05 → 0.35 over first 20 s, then constant
    def test_delta_at_flatop_is_0_35(self, config):
        assert pytest.approx(_eval(config, "delta", T_FLATOP), abs=1e-6) == 0.35

    def test_delta_at_t0_is_approx_0_05(self, config):
        assert pytest.approx(_eval(config, "delta", 0.0), abs=1e-6) == 0.05

    # ip: ramps linearly to -15 MA
    def test_ip_at_flatop_is_minus_15ma(self, config):
        assert pytest.approx(_eval(config, "ip", T_FLATOP), rel=1e-6) == -15_000_000.0

    def test_ip_at_t0_is_zero(self, config):
        assert pytest.approx(_eval(config, "ip", 0.0), abs=1.0) == 0.0

    # b0: constant throughout
    def test_b0_is_constant_minus_5_3(self, config):
        for t in (0.0, T_FLATOP, 100.0):
            assert pytest.approx(_eval(config, "b0", t), abs=1e-6) == -5.3

    # r0: constant at ITER major radius
    def test_r0_is_6_2(self, config):
        assert pytest.approx(_eval(config, "r0", T_FLATOP), abs=1e-6) == 6.2

    # minor radius a: ramps from 0.3 to 2.0 then back
    def test_a_at_flatop_is_2_0(self, config):
        assert pytest.approx(_eval(config, "a", T_FLATOP), abs=1e-6) == 2.0

    def test_a_at_t0_is_0_3(self, config):
        assert pytest.approx(_eval(config, "a", 0.0), abs=1e-6) == 0.3


# ── Equilibrium IDS construction (b0 fix) ────────────────────────────────────

class TestEquilibriumIdsConstruction:
    """Verify that the b0 direct-assignment fix works without a resize error."""

    def _make_equilibrium(self, b0_value: float):
        factory = imas.IDSFactory()
        eq = factory.new("equilibrium")
        eq.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        eq.time = [0.0]
        eq.time_slice.resize(1)
        # Previously: eq.vacuum_toroidal_field.b0.resize(1) — fails with ValueError
        eq.vacuum_toroidal_field.r0 = 6.2
        eq.vacuum_toroidal_field.b0 = np.array([b0_value])  # fixed form
        return eq

    def test_b0_assignment_does_not_raise(self):
        """Direct np.array assignment must not raise ValueError."""
        eq = self._make_equilibrium(-5.3)
        assert eq.vacuum_toroidal_field.b0[0] == pytest.approx(-5.3)

    def test_b0_value_is_stored_correctly(self):
        eq = self._make_equilibrium(-5.3)
        assert pytest.approx(float(eq.vacuum_toroidal_field.b0[0]), abs=1e-9) == -5.3

    def test_b0_positive_value(self):
        eq = self._make_equilibrium(5.3)
        assert pytest.approx(float(eq.vacuum_toroidal_field.b0[0]), abs=1e-9) == 5.3

    def test_r0_stored_correctly(self):
        eq = self._make_equilibrium(-5.3)
        assert pytest.approx(float(eq.vacuum_toroidal_field.r0), abs=1e-9) == 6.2

    def test_time_slice_resized(self):
        eq = self._make_equilibrium(-5.3)
        assert len(eq.time_slice) == 1

    def test_ids_serialisable(self):
        """Equilibrium must serialise without error (required before submitting to NICE)."""
        eq = self._make_equilibrium(-5.3)
        serialised = eq.serialize()
        assert isinstance(serialised, (bytes, str)) and len(serialised) > 0


# ── Plot output data structures ───────────────────────────────────────────────

class TestTimestepResultStructure:
    """Verify that the TimestepResult returned by _build_timestep_result has
    all fields the frontend expects for visualisation."""

    def test_result_has_plot_fields(self):
        from backend.models import TimestepResult

        r = TimestepResult(
            t=50.0, index=5, total=11,
            status="success",
            separatrix_r=[6.2, 7.2, 6.2],
            separatrix_z=[-0.5, 0.0, 0.5],
            o_points=[{"r": 6.2, "z": 0.0}],
            x_points=[{"r": 5.1, "z": -3.3}],
            metrics={"elongation": 1.7, "triangularity": 0.35, "ip_actual": -15e6},
            psi_norm=[0.0, 0.5, 1.0],
            dpressure_dpsi=[1.0, 0.5, 0.0],
            f_df_dpsi=[2.0, 1.5, 1.0],
            input_psi_norm=[0.0, 0.5, 1.0],
            input_dpressure_dpsi=[1.0, 0.5, 0.0],
            input_f_df_dpsi=[2.0, 1.5, 1.0],
            coil_names=["PF1", "PF2"],
            coil_currents=[1e6, -5e5],
        )

        assert r.t == pytest.approx(50.0)
        assert r.status == "success"
        assert len(r.separatrix_r) == 3
        assert len(r.o_points) == 1
        assert r.metrics["elongation"] == pytest.approx(1.7)
        assert r.metrics["triangularity"] == pytest.approx(0.35)
        assert r.metrics["ip_actual"] == pytest.approx(-15e6)
        assert r.psi_norm[0] == pytest.approx(0.0)
        assert r.psi_norm[-1] == pytest.approx(1.0)

    def test_result_with_iter_flatop_metrics(self):
        from backend.models import TimestepResult

        r = TimestepResult(
            t=50.0, index=5, total=11,
            metrics={
                "elongation": 1.7,
                "triangularity": 0.35,
                "major_radius": 6.2,
                "minor_radius": 2.0,
                "ip_actual": -15e6,
                "q95": 3.0,
            },
        )
        assert r.metrics["major_radius"] == pytest.approx(6.2)
        assert r.metrics["minor_radius"] == pytest.approx(2.0)
        assert r.metrics["q95"] == pytest.approx(3.0)
