"""Tests for the FastAPI backend REST endpoints."""
from __future__ import annotations

from textwrap import dedent
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient


# ── YAML fixtures ────────────────────────────────────────────────────────────────

SIMPLE_YAML = dedent("""\
    globals:
      dd_version: 4.0.0
      machine_description: {}

    Test Group:
      const_wave:
      - {type: constant, value: 5.0, duration: 100}
      linear_wave:
      - {type: linear, from: 0.0, to: 10.0, duration: 100}
""")

NICE_YAML = dedent("""\
    globals:
      dd_version: 4.0.0
      machine_description: {}

    NICE Shape:
      kappa:
      - {type: constant, value: 1.8, duration: 100}
      delta:
      - {type: constant, value: 0.43, duration: 100}
      a:
      - {type: constant, value: 1.9, duration: 100}

    NICE Properties:
      ip:
      - {type: linear, from: 0.0, to: -15000000.0, duration: 100}
      b0:
      - {type: constant, value: -5.3, duration: 100}
""")


# ── Fixtures ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_config(tmp_path):
    return tmp_path / "waveform_editor.yaml"


@pytest.fixture
def client(tmp_config):
    with patch("backend.main.CONFIG_FILE", tmp_config):
        from backend.main import app
        with TestClient(app) as c:
            yield c


# ── Settings ─────────────────────────────────────────────────────────────────────

class TestGetSettings:
    def test_returns_defaults_when_no_config(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nice_inv_executable"] == "nice_imas_inv_muscle3"
        assert data["nice_dir_executable"] == "nice_imas_dir_muscle3"
        assert data["nice_mode"] == "NICE Inverse"
        assert data["machine_preset"] == "Custom"
        assert data["md_pf_active"] == ""
        assert data["verbose"] == 1
        assert data["environment"] == {}

    def test_reads_existing_config(self, client, tmp_config):
        config = {
            "nice": {
                "inv_executable": "my_nice",
                "dir_executable": "my_dir",
                "mode": "NICE Direct",
                "machine_preset": "ITER",
                "md_pf_active": "imas:hdf5?path=/some/path",
                "md_pf_passive": "",
                "md_wall": "",
                "md_iron_core": "",
                "verbose": 2,
                "environment": {"MY_VAR": "val"},
            }
        }
        tmp_config.parent.mkdir(parents=True, exist_ok=True)
        tmp_config.write_text(yaml.safe_dump(config))

        resp = client.get("/api/settings")
        data = resp.json()
        assert data["nice_inv_executable"] == "my_nice"
        assert data["nice_mode"] == "NICE Direct"
        assert data["verbose"] == 2
        assert data["environment"]["MY_VAR"] == "val"


class TestSaveSettings:
    def _payload(self, **overrides):
        base = {
            "nice_inv_executable": "nice_imas_inv_muscle3",
            "nice_dir_executable": "nice_imas_dir_muscle3",
            "nice_mode": "NICE Inverse",
            "machine_preset": "Custom",
            "md_pf_active": "",
            "md_pf_passive": "",
            "md_wall": "",
            "md_iron_core": "",
            "verbose": 1,
            "environment": {},
        }
        return {**base, **overrides}

    def test_returns_ok(self, client):
        resp = client.post("/api/settings", json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_creates_config_file(self, client, tmp_config):
        client.post("/api/settings", json=self._payload())
        assert tmp_config.exists()

    def test_config_file_content(self, client, tmp_config):
        client.post("/api/settings", json=self._payload(nice_inv_executable="custom_nice", verbose=3))
        raw = yaml.safe_load(tmp_config.read_text())
        assert raw["nice"]["inv_executable"] == "custom_nice"
        assert raw["nice"]["verbose"] == 3

    def test_roundtrip(self, client):
        payload = self._payload(
            nice_mode="NICE Direct",
            verbose=2,
            environment={"OMP_NUM_THREADS": "4"},
        )
        client.post("/api/settings", json=payload)
        data = client.get("/api/settings").json()
        assert data["nice_mode"] == "NICE Direct"
        assert data["verbose"] == 2
        assert data["environment"]["OMP_NUM_THREADS"] == "4"


# ── YAML parse ────────────────────────────────────────────────────────────────────

class TestParseYaml:
    def test_parse_empty(self, client):
        resp = client.post("/api/yaml/parse", json={"yaml_content": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["waveforms"] == []
        assert data["load_error"] == ""

    def test_parse_single_waveform(self, client):
        yaml_str = dedent("""\
            globals:
              dd_version: 4.0.0
              machine_description: {}

            Group:
              wave1:
              - {type: constant, value: 3.0, duration: 50}
        """)
        resp = client.post("/api/yaml/parse", json={"yaml_content": yaml_str})
        data = resp.json()
        assert len(data["waveforms"]) == 1
        w = data["waveforms"][0]
        assert w["name"] == "wave1"
        assert w["group_path"] == ["Group"]
        assert w["is_derived"] is False

    def test_parse_multiple_waveforms(self, client):
        resp = client.post("/api/yaml/parse", json={"yaml_content": SIMPLE_YAML})
        data = resp.json()
        names = {w["name"] for w in data["waveforms"]}
        assert "const_wave" in names
        assert "linear_wave" in names

    def test_parse_nice_sections(self, client):
        resp = client.post("/api/yaml/parse", json={"yaml_content": NICE_YAML})
        data = resp.json()
        names = {w["name"] for w in data["waveforms"]}
        assert "kappa" in names
        assert "delta" in names
        assert "ip" in names
        assert "b0" in names

    def test_group_path_preserved(self, client):
        resp = client.post("/api/yaml/parse", json={"yaml_content": NICE_YAML})
        data = resp.json()
        kappa = next(w for w in data["waveforms"] if w["name"] == "kappa")
        assert kappa["group_path"] == ["NICE Shape"]

    def test_time_bounds_from_duration(self, client):
        yaml_str = dedent("""\
            globals:
              dd_version: 4.0.0
              machine_description: {}

            Group:
              wave:
              - {type: constant, value: 1.0, duration: 200}
        """)
        resp = client.post("/api/yaml/parse", json={"yaml_content": yaml_str})
        data = resp.json()
        assert data["time_end"] == pytest.approx(200.0)

    def test_yaml_content_echoed_back(self, client):
        resp = client.post("/api/yaml/parse", json={"yaml_content": SIMPLE_YAML})
        data = resp.json()
        assert data["yaml_content"] == SIMPLE_YAML

    def test_invalid_yaml_returns_error(self, client):
        resp = client.post("/api/yaml/parse", json={"yaml_content": "{bad yaml:"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["load_error"] != ""

    def test_derived_waveform_flagged(self, client):
        yaml_str = dedent("""\
            globals:
              dd_version: 4.0.0
              machine_description: {}

            Group:
              base:
              - {type: constant, value: 1.0, duration: 100}
              derived: '"base" * 2'
        """)
        resp = client.post("/api/yaml/parse", json={"yaml_content": yaml_str})
        data = resp.json()
        derived = next((w for w in data["waveforms"] if w["name"] == "derived"), None)
        if derived is not None:
            assert derived["is_derived"] is True

    def test_waveform_at_root_level_raises_load_error(self, client):
        """Regression: tendenciesToYaml bug — waveform at root (no group) must fail gracefully."""
        yaml_str = dedent("""\
            globals:
              dd_version: 4.0.0
              machine_description: {}

            kappa:
            - {type: constant, value: 1.8, duration: 100}
        """)
        resp = client.post("/api/yaml/parse", json={"yaml_content": yaml_str})
        assert resp.status_code == 200
        data = resp.json()
        assert data["load_error"] != ""

    def test_waveform_inside_group_parses_without_error(self, client):
        """Regression: after tendenciesToYaml fix, grouped waveforms must parse cleanly."""
        yaml_str = dedent("""\
            globals:
              dd_version: 4.0.0
              machine_description: {}

            NICE Shape:
              kappa:
              - {type: constant, value: 1.8, duration: 100}
              - {type: constant, value: 1.5, duration: 50}
        """)
        resp = client.post("/api/yaml/parse", json={"yaml_content": yaml_str})
        assert resp.status_code == 200
        data = resp.json()
        assert data["load_error"] == ""
        assert any(w["name"] == "kappa" for w in data["waveforms"])


# ── Waveform evaluate ─────────────────────────────────────────────────────────────

class TestEvaluateWaveforms:
    def test_constant_waveform(self, client):
        yaml_str = dedent("""\
            globals:
              dd_version: 4.0.0
              machine_description: {}

            Group:
              mywave:
              - {type: constant, value: 7.0, duration: 100}
        """)
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": yaml_str,
            "time_points": [0.0, 25.0, 50.0, 75.0, 100.0],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == ""
        assert len(data["waveforms"]) == 1
        w = data["waveforms"][0]
        assert w["name"] == "mywave"
        assert all(abs(v - 7.0) < 1e-9 for v in w["values"])

    def test_linear_ramp(self, client):
        yaml_str = dedent("""\
            globals:
              dd_version: 4.0.0
              machine_description: {}

            Group:
              ramp:
              - {type: linear, from: 0.0, to: 10.0, duration: 10}
        """)
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": yaml_str,
            "time_points": [0.0, 5.0, 10.0],
        })
        data = resp.json()
        w = data["waveforms"][0]
        assert w["values"][0] == pytest.approx(0.0, abs=1e-6)
        assert w["values"][1] == pytest.approx(5.0, abs=1e-6)
        assert w["values"][2] == pytest.approx(10.0, abs=1e-6)

    def test_filter_by_name(self, client):
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": SIMPLE_YAML,
            "time_points": [0.0, 50.0],
            "waveform_names": ["const_wave"],
        })
        data = resp.json()
        assert len(data["waveforms"]) == 1
        assert data["waveforms"][0]["name"] == "const_wave"

    def test_all_waveforms_returned_without_filter(self, client):
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": SIMPLE_YAML,
            "time_points": [0.0, 50.0, 100.0],
        })
        data = resp.json()
        names = {w["name"] for w in data["waveforms"]}
        assert "const_wave" in names
        assert "linear_wave" in names

    def test_times_match_input_points(self, client):
        time_pts = [0.0, 25.0, 50.0, 75.0, 100.0]
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": SIMPLE_YAML,
            "time_points": time_pts,
        })
        data = resp.json()
        w = data["waveforms"][0]
        assert len(w["times"]) == len(time_pts)
        assert len(w["values"]) == len(time_pts)

    def test_invalid_yaml_returns_error(self, client):
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": "{bad yaml:",
            "time_points": [0.0],
        })
        data = resp.json()
        assert data["error"] != ""
        assert data["waveforms"] == []

    def test_nonexistent_waveform_name_skipped(self, client):
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": SIMPLE_YAML,
            "time_points": [0.0],
            "waveform_names": ["does_not_exist"],
        })
        data = resp.json()
        assert data["waveforms"] == []

    def test_nice_shape_waveform(self, client):
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": NICE_YAML,
            "time_points": [0.0, 50.0, 100.0],
            "waveform_names": ["kappa"],
        })
        data = resp.json()
        assert len(data["waveforms"]) == 1
        w = data["waveforms"][0]
        assert all(abs(v - 1.8) < 1e-9 for v in w["values"])


# ── Machine geometries ────────────────────────────────────────────────────────────

class TestMachineGeometries:
    def test_empty_uris_returns_empty_geometry(self, client):
        resp = client.post("/api/machine/geometries", json={
            "md_pf_active_uri": "",
            "md_wall_uri": "",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["coil_rectangles"] == []
        assert data["coil_paths"] == []
        assert data["wall_limiter"] == []
        assert data["vacuum_vessel"] == []

    def test_invalid_uri_gracefully_returns_empty(self, client):
        resp = client.post("/api/machine/geometries", json={
            "md_pf_active_uri": "imas:nonexistent_backend?path=/no/such/path",
            "md_wall_uri": "",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["coil_rectangles"] == []

    def test_missing_pf_active_uri_field_is_optional(self, client):
        resp = client.post("/api/machine/geometries", json={})
        assert resp.status_code == 200


# ── End-to-end workflow ───────────────────────────────────────────────────────────

WORKFLOW_YAML = dedent("""\
    globals:
      dd_version: 4.0.0
      machine_description: {}

    NICE Shape:
      kappa:
      - {type: linear, from: 1.2, to: 1.7, duration: 20}
      - {type: constant, value: 1.7, duration: 60}
      - {type: linear, from: 1.7, to: 1.2, duration: 20}
      delta:
      - {type: constant, value: 0.35, duration: 100}
      a:
      - {type: linear, from: 0.3, to: 2.0, duration: 20}
      - {type: constant, value: 2.0, duration: 60}
      - {type: linear, from: 2.0, to: 0.3, duration: 20}
      center_r:
      - {type: constant, value: 6.2, duration: 100}
      center_z:
      - {type: constant, value: 0.545, duration: 100}

    NICE Properties:
      ip:
      - {type: linear, from: 0.0, to: -15000000.0, duration: 20}
      - {type: constant, value: -15000000.0, duration: 60}
      - {type: linear, from: -15000000.0, to: 0.0, duration: 20}
      b0:
      - {type: constant, value: -5.3, duration: 100}
      r0:
      - {type: constant, value: 6.2, duration: 100}
""")


class TestShapePreviewWorkflow:
    """End-to-end workflow: parse YAML → evaluate shape waveforms → verify values.

    This mirrors the client-side evaluateShapePreview() call that drives the
    animated plasma-outline in EquilibriumPlot.
    """

    def test_parse_then_evaluate_shape_waveforms(self, client):
        # Step 1: parse
        parse_resp = client.post("/api/yaml/parse", json={"yaml_content": WORKFLOW_YAML})
        assert parse_resp.status_code == 200
        parsed = parse_resp.json()
        assert parsed["load_error"] == ""

        tStart = parsed["time_start"]
        tEnd = parsed["time_end"]
        assert tEnd == pytest.approx(100.0)

        # Step 2: evaluate the five NICE Shape parameters at 10 uniform points
        n = 10
        times = [tStart + i / (n - 1) * (tEnd - tStart) for i in range(n)]
        eval_resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": WORKFLOW_YAML,
            "time_points": times,
            "waveform_names": ["kappa", "delta", "a", "center_r", "center_z"],
        })
        assert eval_resp.status_code == 200
        data = eval_resp.json()
        assert data["error"] == ""

        wf = {w["name"]: w["values"] for w in data["waveforms"]}
        assert set(wf) == {"kappa", "delta", "a", "center_r", "center_z"}

        # kappa ramps from 1.2 to 1.7 over first 20 s
        assert wf["kappa"][0] == pytest.approx(1.2, abs=0.01)   # t=0
        assert wf["kappa"][-1] == pytest.approx(1.2, abs=0.01)  # t=100 (after ramp-down)

        # delta is constant throughout
        assert all(abs(v - 0.35) < 1e-6 for v in wf["delta"])

        # a ramps from 0.3 → 2.0 → 0.3; flat top value at mid-range time
        mid_idx = n // 2  # t=~55 s → flat top
        assert wf["a"][mid_idx] == pytest.approx(2.0, abs=0.01)

        # center_r and center_z are constant
        assert all(abs(v - 6.2) < 1e-6 for v in wf["center_r"])

    def test_all_shape_waveforms_present_after_parse(self, client):
        parse_resp = client.post("/api/yaml/parse", json={"yaml_content": WORKFLOW_YAML})
        parsed = parse_resp.json()
        names = {w["name"] for w in parsed["waveforms"]}
        for param in ("kappa", "delta", "a", "center_r", "center_z", "ip", "b0"):
            assert param in names, f"{param} missing from parsed waveforms"

    def test_shape_waveforms_in_correct_groups(self, client):
        parse_resp = client.post("/api/yaml/parse", json={"yaml_content": WORKFLOW_YAML})
        parsed = parse_resp.json()
        wf_map = {w["name"]: w for w in parsed["waveforms"]}
        for name in ("kappa", "delta", "a", "center_r", "center_z"):
            assert wf_map[name]["group_path"] == ["NICE Shape"]
        for name in ("ip", "b0", "r0"):
            assert wf_map[name]["group_path"] == ["NICE Properties"]

    def test_multi_segment_kappa_evaluates_at_flat_top(self, client):
        times = [10.0, 50.0, 90.0]  # ramp-up, flat-top, ramp-down
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": WORKFLOW_YAML,
            "time_points": times,
            "waveform_names": ["kappa"],
        })
        values = resp.json()["waveforms"][0]["values"]
        assert values[1] == pytest.approx(1.7, abs=1e-6)   # flat-top
        assert values[0] < values[1]                        # still ramping at t=10
        assert values[2] < values[1]                        # ramping down at t=90

    def test_ip_ramp_up_then_flat(self, client):
        times = [0.0, 20.0, 50.0, 100.0]
        resp = client.post("/api/waveform/evaluate", json={
            "yaml_content": WORKFLOW_YAML,
            "time_points": times,
            "waveform_names": ["ip"],
        })
        values = resp.json()["waveforms"][0]["values"]
        assert values[0] == pytest.approx(0.0, abs=1e-3)
        assert values[1] == pytest.approx(-15_000_000.0, abs=1.0)
        assert values[2] == pytest.approx(-15_000_000.0, abs=1.0)
        assert values[3] == pytest.approx(0.0, abs=1e-3)
