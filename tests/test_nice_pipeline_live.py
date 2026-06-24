"""Live end-to-end pipeline test using the real NICE binary.

Run with:
    pytest tests/test_nice_pipeline_live.py -v -s

Tests are skipped automatically when:
 - The NICE executable is not on PATH
 - Machine description URIs are not set in ~/.config/waveform_editor.yaml

Designed to iterate: on failure the full NICE output, subprocess exit codes and
error messages are printed so you can fix the root cause and re-run immediately.
"""
from __future__ import annotations

import asyncio
import io
import logging
import multiprocessing
import os
import shutil
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import imas
import numpy as np
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.plasma_shape_calc import compute_outline_from_params
from waveform_editor.shape_editor.plasma_properties_calc import compute_profiles_from_params
import importlib.resources

logger = logging.getLogger(__name__)

ITER_FLATOP_YAML = (
    Path(__file__).parent.parent / "examples" / "iter_15ma_flatop.yaml"
).read_text()


# ── Prerequisites check ────────────────────────────────────────────────────────

def _nice_executable():
    """Return the NICE inv executable path, or None if not found."""
    for name in ("nice_imas_inv_muscle3", "nice_imas_inv"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _load_settings():
    """Load user settings from disk; return empty dict if absent."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    cfg_file = config_home / "waveform_editor.yaml"
    if cfg_file.exists():
        return yaml.safe_load(cfg_file.read_text()) or {}
    return {}


def _machine_uris():
    """Return (pf_active, pf_passive, wall, iron_core) URIs from settings, or None."""
    s = _load_settings().get("nice", {})
    uris = (
        s.get("md_pf_active", ""),
        s.get("md_pf_passive", ""),
        s.get("md_wall", ""),
        s.get("md_iron_core", ""),
    )
    return uris if all(uris) else None


def _load_ids(uri, ids_name):
    """Load an IDS from IMAS; return None and a reason string on failure."""
    if not uri:
        return None, f"URI is empty for {ids_name}"
    try:
        with imas.DBEntry(uri, "r") as entry:
            return entry.get_slice(ids_name, 0, imas.ids_defs.CLOSEST_INTERP), None
    except Exception as e:
        return None, f"Could not load {ids_name} from {uri!r}: {e}"


NICE_EXECUTABLE = _nice_executable()
MACHINE_URIS = _machine_uris()

requires_nice = pytest.mark.skipif(
    NICE_EXECUTABLE is None,
    reason=f"NICE executable not found on PATH (tried: nice_imas_inv_muscle3, nice_imas_inv)",
)
requires_machine_desc = pytest.mark.skipif(
    MACHINE_URIS is None,
    reason="Machine description URIs not configured in ~/.config/waveform_editor.yaml",
)


# ── Diagnostic helpers ─────────────────────────────────────────────────────────

def _diag_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _diag_section(title: str):
    print(f"\n--- {title} ---")


def _eval_waveform_at(config, name, t):
    if name not in config.waveform_map:
        return None
    t_arr = np.array([t])
    grp = config.waveform_map[name]
    wf = grp[name]
    _, vals = wf.get_value(t_arr)
    return float(vals[0])


def _build_equilibrium(factory, config, t, n_bnd_points=96, is_inverse=True):
    """Build the equilibrium IDS exactly as backend/main.py does."""
    from backend.main import (
        SHAPE_WAVEFORM_DEFAULTS,
        PROPERTY_WAVEFORM_DEFAULTS,
    )

    shape = {k: (w if (w := _eval_waveform_at(config, k, t)) is not None else v)
             for k, v in SHAPE_WAVEFORM_DEFAULTS.items()}
    shape["n_bnd_points"] = n_bnd_points

    props = {k: (w if (w := _eval_waveform_at(config, k, t)) is not None else v)
             for k, v in PROPERTY_WAVEFORM_DEFAULTS.items()}

    psi_norm, dpressure_dpsi, f_df_dpsi = compute_profiles_from_params(
        r0=props["r0"],
        alpha=props["profile_alpha"],
        beta=props["profile_beta"],
        gamma=props["profile_gamma"],
    )

    equilibrium = factory.new("equilibrium")
    equilibrium.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
    equilibrium.time = [0.0]
    equilibrium.time_slice.resize(1)

    if is_inverse:
        outline_r, outline_z = compute_outline_from_params(
            a=shape["a"],
            center_r=shape["center_r"],
            center_z=shape["center_z"],
            kappa=shape["kappa"],
            delta=shape["delta"],
            rx=shape["rx"],
            zx=shape["zx"],
            n_desired_bnd_points=shape["n_bnd_points"],
        )
        equilibrium.time_slice[0].boundary.outline.r = outline_r
        equilibrium.time_slice[0].boundary.outline.z = outline_z

    equilibrium.vacuum_toroidal_field.r0 = props["r0"]
    equilibrium.vacuum_toroidal_field.b0 = np.array([props["b0"]])
    ts_eq = equilibrium.time_slice[0]
    ts_eq.global_quantities.ip = props["ip"]
    ts_eq.profiles_1d.dpressure_dpsi = dpressure_dpsi
    ts_eq.profiles_1d.f_df_dpsi = f_df_dpsi
    ts_eq.profiles_1d.psi = psi_norm
    return equilibrium, shape, props


# ── Prerequisite tests (always run) ───────────────────────────────────────────

class TestPrerequisites:
    """Fast checks that print clear guidance when something is missing."""

    def test_nice_executable_on_path(self):
        path = _nice_executable()
        if path is None:
            pytest.fail(
                "NICE executable not found. Expected 'nice_imas_inv_muscle3' on PATH.\n"
                "Add the NICE bin directory to your PATH and re-run."
            )
        print(f"\nNICE found at: {path}")

    def test_machine_descriptions_configured(self):
        uris = _machine_uris()
        if uris is None:
            s = _load_settings()
            nice_section = s.get("nice", {})
            pytest.fail(
                "Machine description URIs not configured.\n"
                f"Config file: ~/.config/waveform_editor.yaml\n"
                f"Current 'nice' section: {nice_section}\n"
                "Set md_pf_active, md_pf_passive, md_wall, md_iron_core."
            )
        print(f"\nMachine description URIs configured: {uris[0][:60]}...")

    @requires_machine_desc
    def test_machine_descriptions_loadable(self):
        uris = _machine_uris()
        ids_names = ("pf_active", "pf_passive", "wall", "iron_core")
        failed = []
        for uri, name in zip(uris, ids_names):
            ids, err = _load_ids(uri, name)
            if ids is None:
                failed.append(f"  {name}: {err}")
            else:
                print(f"\n  {name}: OK (loaded from {uri[:60]}...)")
        if failed:
            pytest.fail("Failed to load machine descriptions:\n" + "\n".join(failed))


# ── IDS construction test (always run) ────────────────────────────────────────

class TestEquilibriumConstruction:
    """Validate IDS construction before touching NICE."""

    def test_flatop_equilibrium_builds_at_all_timesteps(self):
        """Build equilibrium IDS for every 10-s timestep; confirm no exceptions."""
        config = WaveformConfiguration()
        config.load_yaml(ITER_FLATOP_YAML)
        assert config.parser.parse_errors == []

        factory = imas.IDSFactory()
        failures = []
        for t in range(0, 101, 10):
            try:
                eq, shape, props = _build_equilibrium(factory, config, float(t))
                # Verify serializable
                eq.serialize()
                print(f"  t={t:4.0f}: kappa={shape['kappa']:.3f}  "
                      f"ip={props['ip']/1e6:.1f} MA  b0={props['b0']:.2f} T  OK")
            except Exception as e:
                failures.append(f"t={t}: {e}")
        if failures:
            pytest.fail("IDS construction failed:\n" + "\n".join(failures))

    def test_ip_is_zero_at_t0_not_default(self):
        """ip=0.0 at t=0 must not be replaced by the -15 MA default (or-falsy bug)."""
        config = WaveformConfiguration()
        config.load_yaml(ITER_FLATOP_YAML)
        factory = imas.IDSFactory()
        from backend.main import PROPERTY_WAVEFORM_DEFAULTS
        _, _, props = _build_equilibrium(factory, config, 0.0)
        assert props["ip"] == pytest.approx(0.0, abs=1.0), (
            f"ip at t=0 is {props['ip']:.0f} A — should be 0, not the default "
            f"{PROPERTY_WAVEFORM_DEFAULTS['ip']:.0f} A. "
            "The `or v` fallback treats 0.0 as falsy."
        )

    def test_center_z_is_zero_at_t0_not_default(self):
        """center_z=0.0 at t=0 must not be replaced by the 0.545 m default."""
        config = WaveformConfiguration()
        config.load_yaml(ITER_FLATOP_YAML)
        factory = imas.IDSFactory()
        from backend.main import SHAPE_WAVEFORM_DEFAULTS
        _, shape, _ = _build_equilibrium(factory, config, 0.0)
        assert shape["center_z"] == pytest.approx(0.0, abs=1e-6), (
            f"center_z at t=0 is {shape['center_z']} — should be 0.0, not the default "
            f"{SHAPE_WAVEFORM_DEFAULTS['center_z']}."
        )

    def test_b0_assignment_no_resize_error(self):
        factory = imas.IDSFactory()
        eq = factory.new("equilibrium")
        eq.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        eq.time = [0.0]
        eq.time_slice.resize(1)
        # Must not raise ValueError: cannot resize array referenced by another object
        eq.vacuum_toroidal_field.b0 = np.array([-5.3])
        assert float(eq.vacuum_toroidal_field.b0[0]) == pytest.approx(-5.3)


# ── Live NICE tests (require binary + machine descriptions) ────────────────────

class TestNicePipelineLive:
    """Runs the real NICE binary through NiceIntegration.

    All output is captured and printed on failure so you can see exactly what
    NICE printed before crashing.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.nice_output: list[str] = []
        self.factory = imas.IDSFactory()

    def _on_output(self, data):
        text = data.decode(errors="replace") if isinstance(data, bytes) else data
        self.nice_output.append(text)
        sys.stdout.write(f"[NICE] {text}")
        sys.stdout.flush()

    def _dump_nice_output(self):
        _diag_section("NICE stdout/stderr")
        output = "".join(self.nice_output)
        print(output if output else "(no output captured)")

    def _load_xml(self, name):
        return ET.fromstring(
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath(name)
            .read_text()
        )

    async def _run_single_timestep(self, t: float, uris, executable, verbose=1):
        """Run one NICE reconstruction at time t. Returns (success, result_dict)."""
        config = WaveformConfiguration()
        config.load_yaml(ITER_FLATOP_YAML)

        # Load machine descriptions
        pf_active_ids, err = _load_ids(uris[0], "pf_active")
        assert pf_active_ids is not None, f"pf_active: {err}"
        pf_passive_ids, err = _load_ids(uris[1], "pf_passive")
        assert pf_passive_ids is not None, f"pf_passive: {err}"
        wall_ids, err = _load_ids(uris[2], "wall")
        assert wall_ids is not None, f"wall: {err}"
        iron_core_ids, err = _load_ids(uris[3], "iron_core")
        assert iron_core_ids is not None, f"iron_core: {err}"

        xml_inv = self._load_xml("inverse_param.xml")
        xml_inv.find("verbose").text = str(verbose)

        eq, shape, props = _build_equilibrium(self.factory, config, t)

        comm = NiceIntegration(self.factory, on_output=self._on_output)
        try:
            await comm.run(is_direct_mode=False)
            await comm.submit(
                ET.tostring(xml_inv, encoding="unicode"),
                eq.serialize(),
                pf_active_ids.serialize(),
                pf_passive_ids.serialize(),
                wall_ids.serialize(),
                iron_core_ids.serialize(),
            )

            if comm.equilibrium is None:
                return False, {"error": "submit() returned but equilibrium is None"}

            ts = comm.equilibrium.time_slice[0]
            result = {
                "elongation": float(ts.boundary.elongation),
                "triangularity": float(ts.boundary.triangularity),
                "ip_actual": float(ts.global_quantities.ip),
                "q95": float(ts.global_quantities.q_95),
            }
            return True, result
        except Exception as exc:
            return False, {"error": str(exc), "traceback": traceback.format_exc()}
        finally:
            await comm.close()

    @requires_nice
    @requires_machine_desc
    def test_nice_starts_without_crashing(self):
        """NICE must start and not die before we even send data."""
        _diag_header("TEST: NICE startup")

        async def _check():
            comm = NiceIntegration(self.factory, on_output=self._on_output)
            try:
                await comm.run(is_direct_mode=False)
                _diag_section("After run()")
                print(f"  running={comm.running}")
                print(f"  nice_running={comm.nice_running}")
                print(f"  communicator alive={comm.communicator.is_alive()}")
                print(f"  manager alive={comm.manager.is_alive()}")
                # Give NICE 2 seconds to crash if it's going to
                await asyncio.sleep(2.0)
                _diag_section("After 2s wait")
                print(f"  nice_running={comm.nice_running}")
                if not comm.nice_running:
                    self._dump_nice_output()
                    return False, "NICE exited within 2 seconds of starting"
                return True, None
            finally:
                await comm.close()

        ok, reason = asyncio.run(_check())
        self._dump_nice_output()
        assert ok, f"NICE crashed on startup: {reason}"

    @requires_nice
    @requires_machine_desc
    def test_single_timestep_at_flatop(self):
        """Run a single NICE reconstruction at t=50 s (full flat-top conditions)."""
        _diag_header("TEST: Single timestep t=50 (flat-top)")

        uris = _machine_uris()
        executable = NICE_EXECUTABLE

        ok, result = asyncio.run(self._run_single_timestep(50.0, uris, executable, verbose=2))
        self._dump_nice_output()

        if not ok:
            _diag_section("Failure details")
            print(f"  Error: {result['error']}")
            if "traceback" in result:
                print(result["traceback"])
            pytest.fail(f"NICE failed at t=50: {result['error']}")

        _diag_section("Equilibrium results")
        for k, v in result.items():
            print(f"  {k}: {v:.4f}")

        assert result["elongation"] == pytest.approx(1.7, abs=0.3), (
            f"elongation {result['elongation']:.3f} is far from expected 1.7"
        )

    @requires_nice
    @requires_machine_desc
    def test_full_scenario_three_timesteps(self):
        """Run ramp-up, flat-top and ramp-down to validate the full scenario."""
        _diag_header("TEST: Full scenario (t=0, 50, 100)")

        uris = _machine_uris()
        timesteps = [0.0, 50.0, 100.0]
        results = {}
        failures = []

        for t in timesteps:
            print(f"\n>>> Running t={t}")
            ok, r = asyncio.run(
                self._run_single_timestep(t, uris, NICE_EXECUTABLE, verbose=1)
            )
            self._dump_nice_output()
            self.nice_output.clear()

            if ok:
                results[t] = r
                print(f"    elongation={r['elongation']:.3f}  "
                      f"ip_actual={r['ip_actual']/1e6:.2f} MA  "
                      f"q95={r['q95']:.2f}")
            else:
                failures.append(f"t={t}: {r['error']}")
                print(f"    FAILED: {r['error']}")

        if failures:
            pytest.fail(
                f"NICE failed for {len(failures)}/{len(timesteps)} timesteps:\n"
                + "\n".join(failures)
            )

    @requires_nice
    @requires_machine_desc
    def test_consecutive_timesteps_no_state_leak(self):
        """Run two consecutive timesteps through the same NiceIntegration instance."""
        _diag_header("TEST: Consecutive timesteps (same NiceIntegration instance)")

        uris = _machine_uris()
        config = WaveformConfiguration()
        config.load_yaml(ITER_FLATOP_YAML)

        xml_inv = self._load_xml("inverse_param.xml")
        xml_inv.find("verbose").text = "1"

        async def _run():
            comm = NiceIntegration(self.factory, on_output=self._on_output)
            results = []
            try:
                await comm.run(is_direct_mode=False)

                pf_active_ids, _ = _load_ids(uris[0], "pf_active")
                pf_passive_ids, _ = _load_ids(uris[1], "pf_passive")
                wall_ids, _ = _load_ids(uris[2], "wall")
                iron_core_ids, _ = _load_ids(uris[3], "iron_core")

                for t in [20.0, 50.0]:
                    eq, _, _ = _build_equilibrium(self.factory, config, t)
                    try:
                        await comm.submit(
                            ET.tostring(xml_inv, encoding="unicode"),
                            eq.serialize(),
                            pf_active_ids.serialize(),
                            pf_passive_ids.serialize(),
                            wall_ids.serialize(),
                            iron_core_ids.serialize(),
                        )
                        if comm.equilibrium is not None:
                            ts = comm.equilibrium.time_slice[0]
                            results.append({
                                "t": t,
                                "ok": True,
                                "elongation": float(ts.boundary.elongation),
                            })
                        else:
                            results.append({"t": t, "ok": False, "error": "equilibrium is None"})
                    except Exception as e:
                        results.append({"t": t, "ok": False, "error": str(e)})
            finally:
                await comm.close()
            return results

        results = asyncio.run(_run())
        self._dump_nice_output()

        for r in results:
            status = "OK" if r["ok"] else f"FAILED: {r.get('error')}"
            print(f"  t={r['t']}: {status}"
                  + (f"  elongation={r['elongation']:.3f}" if r.get("ok") else ""))

        failed = [r for r in results if not r["ok"]]
        assert not failed, (
            "Some timesteps failed in consecutive run:\n"
            + "\n".join(f"  t={r['t']}: {r.get('error')}" for r in failed)
        )


# ── Quick smoke test — run without needing NICE installed ─────────────────────

class TestPipelineSmoke:
    """Fast checks that always run — catch regressions without NICE."""

    def test_nice_output_is_forwarded_not_discarded(self):
        """backend/main.py must not use `lambda s: None` for on_output."""
        import ast
        src = Path(__file__).parent.parent / "backend" / "main.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                # Look for lambda with a single arg whose body is None
                body = node.body
                if isinstance(body, ast.Constant) and body.value is None:
                    # Check the lambda is near NiceIntegration
                    pytest.fail(
                        f"backend/main.py line {node.lineno}: "
                        "'lambda s: None' discards NICE output — use a real on_output callback."
                    )

    def test_submit_raises_on_connection_error(self):
        """submit() must raise RuntimeError (not swallow) when NICE pipe dies."""
        import inspect
        src = Path(__file__).parent.parent / "waveform_editor" / "shape_editor" / "nice_integration.py"
        text = src.read_text()
        assert "raise RuntimeError" in text, (
            "nice_integration.py should re-raise on connection errors in submit()"
        )
        assert "running = False" in text, (
            "nice_integration.py should set running=False when NICE crashes"
        )

    def test_websocket_loop_breaks_after_nice_crash(self):
        """backend/main.py must break the timestep loop when communicator.running is False."""
        src = Path(__file__).parent.parent / "backend" / "main.py"
        text = src.read_text()
        assert "if not communicator.running:" in text and "break" in text, (
            "backend/main.py must break the timestep loop when NICE crashes"
        )
