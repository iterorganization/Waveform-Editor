import imas
import numpy as np
import pytest

# libmuscle and ymmsl are optional dependencies, so may not be installed
libmuscle = pytest.importorskip("libmuscle")
ymmsl = pytest.importorskip("ymmsl")

# This cannot be imported if libmuscle is not available
from waveform_editor.muscle3 import (  # noqa: E402
    _time_base_and_base_ids,
    waveform_actor,
)

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


# --- whole-trace mode: an '<ids>_in' port carrying an IDS -> overlay on its /time ----

TRACE_YAML = """
equilibrium:
  equilibrium/time_slice/global_quantities/ip:
    - {to: 8.33e5, duration: 20}
    - {type: constant, duration: 20}
    - {duration: 25, to: 0}
globals:
  dd_version: 4.0.0
"""
# Same waveform as the per-slice test, but now interpolated onto a whole trace at once:
TRACE_TIMES = [1.0, 21.0, 50.0]
TRACE_IP = [8.33e5 / 20, 8.33e5, 8.33e5 * 15 / 25]
BOUNDARY_R = [4.0, 5.0, 6.0]  # pre-existing data the overlay must preserve

TRACE_YMMSL = """
ymmsl_version: v0.1

model:
  name: test_waveform_actor_trace

  components:
    trace_generator:
      implementation: trace_generator
    waveform_actor:
      implementation: waveform_actor
    trace_validator:
      implementation: trace_validator

  conduits:
    trace_generator.output: waveform_actor.equilibrium_in
    waveform_actor.equilibrium_out: trace_validator.equilibrium_in

settings:
  waveform_actor.waveforms: {waveform_yaml}
"""


def trace_generator():
    instance = libmuscle.Instance({ymmsl.Operator.O_I: ["output"]})

    while instance.reuse_instance():
        # Send a whole-trace equilibrium with pre-existing data (a boundary outline);
        # the actor reads /time, overlays Ip, and must preserve the rest in place.
        eq = imas.IDSFactory("4.0.0").equilibrium()
        eq.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        eq.time = TRACE_TIMES
        eq.time_slice.resize(len(TRACE_TIMES))
        for ts in eq.time_slice:
            ts.boundary.outline.r = BOUNDARY_R
        instance.send("output", libmuscle.Message(TRACE_TIMES[0], data=eq.serialize()))


def trace_validator():
    instance = libmuscle.Instance({ymmsl.Operator.F_INIT: ["equilibrium_in"]})

    i = 0
    while instance.reuse_instance():
        msg = instance.receive("equilibrium_in")
        ids = imas.IDSFactory("4.0.0").equilibrium()
        ids.deserialize(msg.data)

        # A single message now carries the full trace interpolated on the input /time:
        assert np.array_equal(ids.time, TRACE_TIMES)
        assert len(ids.time_slice) == len(TRACE_TIMES)
        ip = [ts.global_quantities.ip for ts in ids.time_slice]
        assert np.allclose(ip, TRACE_IP)
        # ... and the incoming IDS' other data is preserved (overlay, not replace):
        for ts in ids.time_slice:
            assert np.array_equal(ts.boundary.outline.r, BOUNDARY_R)
        i += 1
    assert i == 1


@pytest.mark.filterwarnings("ignore:.*use of fork():DeprecationWarning")
def test_muscle3_whole_trace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    waveform_yaml = (tmp_path / "trace.yml").resolve()
    waveform_yaml.write_text(TRACE_YAML)
    configuration = ymmsl.load(TRACE_YMMSL.format(waveform_yaml=waveform_yaml))
    implementations = {
        "trace_generator": trace_generator,
        "waveform_actor": waveform_actor,
        "trace_validator": trace_validator,
    }
    libmuscle.runner.run_simulation(configuration, implementations)


# --- overlay-mode validation of the incoming base IDS ---------------------------------


class _Msg:
    """Minimal stand-in for a libmuscle Message (only the fields the helper reads)."""

    def __init__(self, data, timestamp=0.0):
        self.data = data
        self.timestamp = timestamp


def _eq_msg(homogeneous_time, time):
    eq = imas.IDSFactory("4.0.0").equilibrium()
    eq.ids_properties.homogeneous_time = homogeneous_time
    if time is not None:
        eq.time = time
    return _Msg(eq.serialize())


def test_overlay_non_homogeneous_warns(caplog):
    """A non-homogeneous base is overlaid but warns; INFO names the selected mode."""
    msg = _eq_msg(imas.ids_defs.IDS_TIME_MODE_HETEROGENEOUS, TRACE_TIMES)
    with caplog.at_level("INFO"):
        times, base_idss = _time_base_and_base_ids(msg, "equilibrium_in", "4.0.0")
    assert np.array_equal(times, TRACE_TIMES)
    assert set(base_idss) == {"equilibrium"}
    assert "overlay mode" in caplog.text
    assert "homogeneous time mode" in caplog.text


def test_overlay_homogeneous_does_not_warn(caplog):
    msg = _eq_msg(imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS, TRACE_TIMES)
    with caplog.at_level("WARNING"):
        _time_base_and_base_ids(msg, "equilibrium_in", "4.0.0")
    assert "homogeneous time mode" not in caplog.text


def test_overlay_missing_time_raises():
    msg = _eq_msg(imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS, None)
    with pytest.raises(RuntimeError, match="no root '/time'"):
        _time_base_and_base_ids(msg, "equilibrium_in", "4.0.0")


def test_fresh_export_mode(caplog):
    """A port whose name is not a valid IDS selects fresh-export mode."""
    with caplog.at_level("INFO"):
        times, base_idss = _time_base_and_base_ids(_Msg(None, 3.0), "input", "4.0.0")
    assert np.array_equal(times, [3.0]) and base_idss == {}
    assert "fresh-export mode" in caplog.text
