import imas
import numpy as np
import pytest

# libmuscle and ymmsl are optional dependencies, so may not be installed
libmuscle = pytest.importorskip("libmuscle")
ymmsl = pytest.importorskip("ymmsl")

# This cannot be imported if libmuscle is not available
from waveform_editor.muscle3 import waveform_actor  # noqa: E402

# imas_core is required for IDS serialize, unfortunately this means we cannot run these
# tests in github Actions yet..
pytest.importorskip("imas_core")


WAVEFORM_YAML = """
ec_launchers:
  beams:
    ec_launchers/beam(1)/phase/angle: 1
    ec_launchers/beam(2)/phase/angle: 2
    ec_launchers/beam(3)/phase/angle: 3
    ec_launchers/beam(4)/power_launched/data:
        - {to: 8.33e5, duration: 20}
        - {type: constant, duration: 20}
        - {duration: 25, to: 0}
globals:
  dd_version: 4.0.0
"""
TIMES = [1, 21, 50]
VALUES_PER_TIME = [8.33e5 / 20, 8.33e5, 8.33e5 * 15 / 25]

YMMSL = """
ymmsl_version: v0.1

model:
  name: test_waveform_actor

  components:
    time_generator:
      implementation: time_generator
    waveform_actor:
      implementation: waveform_actor
    waveform_validator:
      implementation: waveform_validator

  conduits:
    time_generator.output: waveform_actor.input
    waveform_actor.ec_launchers_out: waveform_validator.ec_launchers_in

settings:
  waveform_actor.waveforms: {waveform_yaml}
"""


def time_generator():
    instance = libmuscle.Instance({ymmsl.Operator.O_I: ["output"]})

    while instance.reuse_instance():
        for t in TIMES:
            instance.send("output", libmuscle.Message(t))


def waveform_validator():
    instance = libmuscle.Instance({ymmsl.Operator.F_INIT: ["ec_launchers_in"]})

    i = 0
    while instance.reuse_instance():
        msg = instance.receive("ec_launchers_in")
        assert msg.timestamp == TIMES[i]

        ids = imas.IDSFactory("4.0.0").ec_launchers()
        ids.deserialize(msg.data)

        assert np.array_equal(ids.time, [TIMES[i]])
        assert len(ids.beam) == 4
        assert np.array_equal(ids.beam[0].phase.angle, [1])
        assert np.array_equal(ids.beam[1].phase.angle, [2])
        assert np.array_equal(ids.beam[2].phase.angle, [3])
        assert np.allclose(ids.beam[3].power_launched.data, [VALUES_PER_TIME[i]])

        i += 1
    assert i == len(TIMES)


# Running `os.fork()` after `import pandas` triggers this warning...
# It doesn't seem to be an issue (and not relevant in production where muscle_manager
# will start the actor in a standalone process), so we'll ignore this warning:
@pytest.mark.filterwarnings("ignore:.*use of fork():DeprecationWarning")
def test_muscle3(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    waveform_yaml = (tmp_path / "waveform.yml").resolve()
    waveform_yaml.write_text(WAVEFORM_YAML)
    configuration = ymmsl.load(YMMSL.format(waveform_yaml=waveform_yaml))
    implementations = {
        "time_generator": time_generator,
        "waveform_actor": waveform_actor,
        "waveform_validator": waveform_validator,
    }
    libmuscle.runner.run_simulation(configuration, implementations)
