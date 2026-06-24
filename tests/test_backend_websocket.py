"""Tests for the NICE WebSocket endpoint error paths.

Notes:
- Only the invalid-YAML path is tested here because it returns before any
  run_in_executor calls; it is therefore fast and deterministic.
- The machine-descriptions error path requires run_in_executor to complete,
  which has reliability issues in starlette's TestClient under Python 3.14
  + anyio. Those paths are covered by integration tests.
"""
from __future__ import annotations

from textwrap import dedent
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


VALID_YAML = dedent("""\
    globals:
      dd_version: 4.0.0
      machine_description: {}

    NICE Shape:
      kappa:
      - {type: constant, value: 1.8, duration: 100}

    NICE Properties:
      ip:
      - {type: constant, value: -15000000.0, duration: 100}
""")


@pytest.fixture
def client(tmp_path):
    config_file = tmp_path / "config.yaml"
    with patch("backend.main.CONFIG_FILE", config_file):
        from backend.main import app
        with TestClient(app) as c:
            yield c


# ── Invalid YAML — error is returned before any executor calls ────────────────────

class TestWebSocketInvalidYaml:
    def test_bad_yaml_receives_single_error_message(self, client):
        """Server must reply with {type: error} for invalid YAML content."""
        with client.websocket_connect("/ws/nice") as ws:
            ws.send_json({
                "yaml_content": "{not valid yaml: [",
                "timesteps": [0.0],
            })
            msg = ws.receive_json()

        assert msg["type"] == "error"
        assert msg["message"] != ""

    def test_error_message_before_any_status(self, client):
        """For bad YAML the error arrives as the very first message (no status first)."""
        with client.websocket_connect("/ws/nice") as ws:
            ws.send_json({
                "yaml_content": ":::invalid",
                "timesteps": [],
            })
            msg = ws.receive_json()

        # There is no prior "Loading..." status — error is immediate
        assert msg["type"] == "error"

    def test_error_has_non_empty_message_field(self, client):
        with client.websocket_connect("/ws/nice") as ws:
            ws.send_json({
                "yaml_content": "{",
                "timesteps": [],
            })
            msg = ws.receive_json()

        assert "message" in msg
        assert len(msg["message"]) > 0

    def test_error_type_field_is_string(self, client):
        with client.websocket_connect("/ws/nice") as ws:
            ws.send_json({
                "yaml_content": "- bad: [incomplete",
                "timesteps": [],
            })
            msg = ws.receive_json()

        assert isinstance(msg["type"], str)
        assert msg["type"] == "error"


# ── Valid YAML → status message sent before machine descriptions loading ──────────

class TestWebSocketValidYamlFirstMessage:
    def test_valid_yaml_receives_status_as_first_message(self, client):
        """When YAML is valid, the first message must be a 'status' (not 'error')."""
        with client.websocket_connect("/ws/nice") as ws:
            ws.send_json({
                "yaml_content": VALID_YAML,
                "timesteps": [0.0],
                "md_pf_active_uri": "",
                "md_pf_passive_uri": "",
                "md_wall_uri": "",
                "md_iron_core_uri": "",
            })
            msg = ws.receive_json()

        # Regardless of what happens after, first message is always "status"
        assert msg["type"] == "status"
        assert "machine description" in msg["message"].lower()
