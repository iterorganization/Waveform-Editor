import subprocess
from pathlib import Path

import pytest

pytest.importorskip("libmuscle")
pytest.importorskip("imas_core")


def test_muscle3_integration(tmp_path, monkeypatch):
    # Prepare yMMSL file:
    curpath = Path(__file__).parent
    ymmsl_in = curpath / "coupling.ymmsl.in"
    ymmsl_out = curpath / "coupling.ymmsl"
    ymmsl_out.write_text(ymmsl_in.read_text().replace("__PATH__", str(curpath)))

    # Start workflow and check that it completes successfully
    subprocess.run(
        ["muscle_manager", "--start-all", str(ymmsl_out)],
        cwd=tmp_path,
        check=True,
    )
