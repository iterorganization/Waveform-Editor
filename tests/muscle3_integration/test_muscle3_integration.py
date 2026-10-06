import subprocess
from pathlib import Path

import pytest

pytest.importorskip("libmuscle")
pytest.importorskip("imas_core")


def _run_coupling(tmp_path, name):
    # Prepare yMMSL file:
    curpath = Path(__file__).parent
    ymmsl_in = curpath / f"{name}.ymmsl.in"
    ymmsl_out = curpath / f"{name}.ymmsl"
    ymmsl_out.write_text(ymmsl_in.read_text().replace("__PATH__", str(curpath)))

    # Start workflow and check that it completes successfully
    subprocess.run(
        ["muscle_manager", "--start-all", str(ymmsl_out)],
        cwd=tmp_path,
        check=True,
    )


def test_muscle3_integration(tmp_path):
    """One time slice per message: the actor is driven with a timestamp per call."""
    _run_coupling(tmp_path, "coupling")


def test_muscle3_whole_trace_integration(tmp_path):
    """A whole trace in one message: the actor evaluates every time slice at once."""
    _run_coupling(tmp_path, "whole_trace")
