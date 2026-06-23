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
    """Fresh-export mode: the actor is driven with timestamps."""
    _run_coupling(tmp_path, "coupling")


def test_muscle3_overlay_integration(tmp_path):
    """Overlay mode: the actor augments an equilibrium flowing through it."""
    _run_coupling(tmp_path, "overlay")
