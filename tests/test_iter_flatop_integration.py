"""End-to-end integration tests for the ITER 15 MA flat-top example.

Tests the full WebSocket pipeline:
  YAML → IDS construction (b0 fix) → NiceIntegration.submit() → result building → WS messages

NiceIntegration is replaced with a fake that returns valid IMAS data, so the
tests run without a NICE installation while exercising every other layer.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import imas
import numpy as np
import pytest
from fastapi.testclient import TestClient

ITER_FLATOP_YAML = (
    Path(__file__).parent.parent / "examples" / "iter_15ma_flatop.yaml"
).read_text()

# Three representative timesteps: ramp-up, flat-top, ramp-down
TIMESTEPS = [0.0, 50.0, 100.0]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fake_equilibrium(factory, ip=-15e6, b0=-5.3):
    """Minimal valid IMAS equilibrium IDS resembling NICE output."""
    eq = factory.new("equilibrium")
    eq.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
    eq.time = [0.0]
    eq.time_slice.resize(1)
    ts = eq.time_slice[0]

    n = 24
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ts.boundary.outline.r = 6.2 + 2.0 * np.cos(theta)
    ts.boundary.outline.z = 1.7 * 2.0 * np.sin(theta)
    ts.boundary.elongation = 1.7
    ts.boundary.triangularity = 0.35
    ts.boundary.triangularity_upper = 0.32
    ts.boundary.triangularity_lower = 0.38
    ts.boundary.geometric_axis.r = 6.2
    ts.boundary.geometric_axis.z = 0.0
    ts.boundary.minor_radius = 2.0
    ts.global_quantities.ip = ip
    ts.global_quantities.q_95 = 3.2

    psi = np.linspace(0.0, 1.0, 50)
    ts.profiles_1d.psi = psi
    ts.profiles_1d.dpressure_dpsi = np.linspace(1.0, 0.0, 50)
    ts.profiles_1d.f_df_dpsi = np.linspace(2.0, 1.0, 50)

    eq.vacuum_toroidal_field.r0 = 6.2
    eq.vacuum_toroidal_field.b0 = np.array([b0])
    return eq


def _fake_machine_ids(factory, ids_name):
    ids = factory.new(ids_name)
    ids.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_INDEPENDENT
    return ids


# ── Fake NiceIntegration ───────────────────────────────────────────────────────

class _FakeNice:
    """Drop-in for NiceIntegration — returns valid equilibria without a NICE binary."""

    def __init__(self, factory, on_output=None):
        self.factory = factory
        self.on_output = on_output
        self.running = False
        self.equilibrium = None
        self.pf_active = None
        self.processing = False
        self.submit_count = 0

    async def run(self, is_direct_mode=False):
        self.running = True

    async def submit(self, xml_params, equilibrium, pf_active, pf_passive, wall, iron_core):
        if self.processing:
            raise RuntimeError("NICE is already processing an equilibrium reconstruction")
        self.processing = True
        self.submit_count += 1
        self.equilibrium = _fake_equilibrium(self.factory)
        self.pf_active = _fake_machine_ids(self.factory, "pf_active")
        self.processing = False

    async def close(self):
        self.running = False


class _FakeCrashingNice(_FakeNice):
    """Mirrors the fixed NiceIntegration.submit() when NICE crashes.

    Real submit() catches (EOFError, ConnectionResetError, OSError), sets
    processing=False and running=False, then raises RuntimeError — mirrored
    here so the websocket handler sees the same signals.
    """

    async def submit(self, xml_params, equilibrium, pf_active, pf_passive, wall, iron_core):
        self.processing = False
        self.running = False  # signals dead pipeline to the websocket handler
        raise RuntimeError("NICE process terminated unexpectedly")


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _ws_payload(timesteps=None, yaml=ITER_FLATOP_YAML):
    return {
        "yaml_content": yaml,
        "timesteps": timesteps if timesteps is not None else TIMESTEPS,
        # non-empty URIs so _load_ids_sync is actually called (we mock it below)
        "md_pf_active_uri": "imas:hdf5?path=/fake/pf_active",
        "md_pf_passive_uri": "imas:hdf5?path=/fake/pf_passive",
        "md_wall_uri": "imas:hdf5?path=/fake/wall",
        "md_iron_core_uri": "imas:hdf5?path=/fake/iron_core",
        "nice_mode": "NICE Inverse",
        "inv_executable": "nice_imas_inv_muscle3",
    }


def _machine_ids_loader(factory):
    """Return a _load_ids_sync replacement that always produces valid IDS objects."""
    def _loader(uri, ids_name):
        return _fake_machine_ids(factory, ids_name)
    return _loader


@pytest.fixture
def nice_client(tmp_path):
    """TestClient with NiceIntegration, _load_ids_sync, and shutil.which all mocked."""
    factory = imas.IDSFactory()
    config_file = tmp_path / "config.yaml"

    fake_nice_instance = _FakeNice(factory)

    with (
        patch("backend.main.CONFIG_FILE", config_file),
        patch("backend.main._load_ids_sync", side_effect=_machine_ids_loader(factory)),
        patch("backend.main.shutil.which", return_value="/usr/bin/nice_imas_inv_muscle3"),
        patch("backend.main.NiceIntegration", return_value=fake_nice_instance),
    ):
        from backend.main import app
        with TestClient(app) as c:
            yield c, fake_nice_instance


@pytest.fixture
def crashing_nice_client(tmp_path):
    """TestClient where NICE crashes on the first submit."""
    factory = imas.IDSFactory()
    config_file = tmp_path / "config.yaml"

    fake_nice_instance = _FakeCrashingNice(factory)

    with (
        patch("backend.main.CONFIG_FILE", config_file),
        patch("backend.main._load_ids_sync", side_effect=_machine_ids_loader(factory)),
        patch("backend.main.shutil.which", return_value="/usr/bin/nice_imas_inv_muscle3"),
        patch("backend.main.NiceIntegration", return_value=fake_nice_instance),
    ):
        from backend.main import app
        with TestClient(app) as c:
            yield c, fake_nice_instance


def _drain(ws, expected_types: list[str]) -> list[dict]:
    """Receive exactly len(expected_types) messages and assert their types."""
    msgs = []
    for expected in expected_types:
        msg = ws.receive_json()
        assert msg["type"] == expected, f"expected {expected!r}, got {msg['type']!r}: {msg}"
        msgs.append(msg)
    return msgs


# ── Happy-path integration tests ──────────────────────────────────────────────

class TestIterFlatopHappyPath:
    """Full pipeline succeeds: correct message sequence and result contents."""

    def _run(self, client_fixture, timesteps=TIMESTEPS):
        client, nice = client_fixture
        messages = []
        with client.websocket_connect("/ws/nice") as ws:
            ws.send_json(_ws_payload(timesteps))
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] in ("completed", "error"):
                    break
        return messages, nice

    def test_message_sequence_starts_with_status_then_started(self, nice_client):
        msgs, _ = self._run(nice_client)
        types = [m["type"] for m in msgs]
        assert types[0] == "status"
        assert "started" in types

    def test_message_sequence_ends_with_completed(self, nice_client):
        msgs, _ = self._run(nice_client)
        assert msgs[-1]["type"] == "completed"

    def test_one_timestep_result_per_timestep(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        assert len(results) == len(TIMESTEPS)

    def test_submit_called_once_per_timestep(self, nice_client):
        _, nice = self._run(nice_client)
        assert nice.submit_count == len(TIMESTEPS)

    def test_timestep_results_have_success_status(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        for r in results:
            assert r["status"] == "success", f"t={r.get('t')}: {r.get('error')}"

    def test_timestep_results_have_correct_t_values(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        got_times = sorted(r["t"] for r in results)
        assert got_times == pytest.approx(sorted(TIMESTEPS))

    def test_timestep_results_have_separatrix(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        for r in results:
            assert len(r["separatrix_r"]) > 0, "separatrix_r should be populated"
            assert len(r["separatrix_z"]) > 0, "separatrix_z should be populated"

    def test_timestep_results_have_equilibrium_metrics(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        for r in results:
            m = r["metrics"]
            assert "elongation" in m
            assert "triangularity" in m
            assert pytest.approx(m["elongation"], abs=0.01) == 1.7
            assert pytest.approx(m["triangularity"], abs=0.01) == 0.35

    def test_timestep_results_have_profile_data(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        for r in results:
            assert len(r["psi_norm"]) > 0
            assert len(r["dpressure_dpsi"]) > 0
            assert len(r["f_df_dpsi"]) > 0

    def test_timestep_results_have_input_profiles(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        for r in results:
            assert len(r["input_psi_norm"]) > 0
            assert len(r["input_dpressure_dpsi"]) > 0
            assert len(r["input_f_df_dpsi"]) > 0

    def test_psi_norm_ranges_from_0_to_1(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        for r in results:
            if r["psi_norm"]:
                assert r["psi_norm"][0] == pytest.approx(0.0, abs=1e-6)
                assert r["psi_norm"][-1] == pytest.approx(1.0, abs=1e-6)

    def test_index_and_total_are_correct(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        total = len(TIMESTEPS)
        for i, r in enumerate(results):
            assert r["total"] == total
            assert 0 <= r["index"] < total

    def test_completed_message_has_correct_total(self, nice_client):
        msgs, _ = self._run(nice_client)
        completed = next(m for m in msgs if m["type"] == "completed")
        assert completed["total"] == len(TIMESTEPS)

    def test_input_values_present_in_results(self, nice_client):
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        for r in results:
            iv = r.get("input_values", {})
            assert "kappa" in iv
            assert "ip" in iv
            assert "b0" in iv

    def test_iter_flatop_kappa_in_results(self, nice_client):
        """At flat-top (t=50), kappa should be 1.7."""
        msgs, _ = self._run(nice_client)
        results = {m["t"]: m for m in msgs if m["type"] == "timestep_result"}
        r50 = results.get(50.0)
        if r50 and r50.get("input_values"):
            assert pytest.approx(r50["input_values"]["kappa"], abs=0.01) == 1.7

    def test_iter_flatop_b0_in_results(self, nice_client):
        """b0 should be constant at -5.3 T throughout the scenario."""
        msgs, _ = self._run(nice_client)
        results = [m for m in msgs if m["type"] == "timestep_result"]
        for r in results:
            if r.get("input_values"):
                assert pytest.approx(r["input_values"]["b0"], abs=0.01) == -5.3


# ── Crash-recovery integration tests ─────────────────────────────────────────

class TestIterFlatopNiceCrashRecovery:
    """When NICE crashes the pipeline aborts cleanly — no 'already processing' spam."""

    def _run_all(self, crashing_nice_client):
        client, nice = crashing_nice_client
        messages = []
        with client.websocket_connect("/ws/nice") as ws:
            ws.send_json(_ws_payload())
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] in ("completed", "error"):
                    break
        return messages, nice

    def test_crash_does_not_produce_already_processing_error(self, crashing_nice_client):
        msgs, _ = self._run_all(crashing_nice_client)
        error_texts = [
            m.get("error", "") for m in msgs if m["type"] == "timestep_result"
        ]
        for txt in error_texts:
            assert "already processing" not in txt.lower(), (
                f"'already processing' leaked into errors: {error_texts}"
            )

    def test_crash_produces_at_most_one_error_result(self, crashing_nice_client):
        """After NICE crashes the loop should break, not emit N error results."""
        msgs, _ = self._run_all(crashing_nice_client)
        error_results = [
            m for m in msgs if m["type"] == "timestep_result" and m["status"] == "error"
        ]
        # Only the t=0 timestep should produce an error; the rest are skipped
        assert len(error_results) == 1, (
            f"Expected 1 error result, got {len(error_results)}: "
            + str([r.get("error") for r in error_results])
        )

    def test_crash_result_has_correct_error_type(self, crashing_nice_client):
        msgs, _ = self._run_all(crashing_nice_client)
        error_results = [
            m for m in msgs if m["type"] == "timestep_result" and m["status"] == "error"
        ]
        assert len(error_results) >= 1
        assert "NICE process terminated" in error_results[0]["error"]

    def test_pipeline_still_ends_with_completed(self, crashing_nice_client):
        """Even after a crash the pipeline must send 'completed' so the UI unblocks."""
        msgs, _ = self._run_all(crashing_nice_client)
        assert msgs[-1]["type"] == "completed"
