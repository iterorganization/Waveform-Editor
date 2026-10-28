import imas
import numpy as np
import pytest

from tests.conftest import TEST_DD_VERSION

# libmuscle and ymmsl are optional dependencies, so may not be installed
libmuscle = pytest.importorskip("libmuscle")
ymmsl = pytest.importorskip("ymmsl")

# This cannot be imported if libmuscle is not available
from waveform_editor.muscle3 import _export_times, waveform_actor  # noqa: E402

# imas_core is required for IDS serialize, unfortunately this means we cannot run these
# tests in github Actions yet..
pytest.importorskip("imas_core")


WAVEFORM_YAML = f"""
dd_version: {TEST_DD_VERSION}
output:
  ec_launchers:
    beams:
      ec_launchers/beam(1)/phase/angle: 1
      ec_launchers/beam(2)/phase/angle: 2
      ec_launchers/beam(3)/phase/angle: 3
      ec_launchers/beam(4)/power_launched/data:
          - {{to: 8.33e5, duration: 20}}
          - {{type: constant, duration: 20}}
          - {{duration: 25, to: 0}}
"""
TIMES = [1, 21, 50]
VALUES_PER_TIME = [8.33e5 / 20, 8.33e5, 8.33e5 * 15 / 25]

YMMSL = """
ymmsl_version: v0.2

models:
  test_waveform_actor:
    components:
      time_generator:
        description: Emits a fixed time sequence
        implementation: time_generator
        ports:
          o_i: [output]
      waveform_actor:
        description: The actor under test
        implementation: waveform_actor
        ports:
          f_init: [ec_launchers_in]
          o_f: [ec_launchers_out]
      waveform_validator:
        description: Validates the exported waveform
        implementation: waveform_validator
        ports:
          f_init: [ec_launchers_in]

    conduits:
      time_generator.output: waveform_actor.ec_launchers_in
      waveform_actor.ec_launchers_out: waveform_validator.ec_launchers_in

settings:
  waveform_actor.waveforms: {waveform_yaml}
"""


def time_generator():
    instance = libmuscle.Instance({ymmsl.Operator.O_I: ["output"]})

    while instance.reuse_instance():
        for t in TIMES:
            # Only the root /time of this IDS is used by the actor; everything else
            # about it is ignored.
            carrier = imas.IDSFactory(TEST_DD_VERSION).ec_launchers()
            carrier.ids_properties.homogeneous_time = (
                imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
            )
            carrier.time = [t]
            instance.send("output", libmuscle.Message(t, data=carrier.serialize()))


def waveform_validator():
    instance = libmuscle.Instance({ymmsl.Operator.F_INIT: ["ec_launchers_in"]})

    i = 0
    while instance.reuse_instance():
        msg = instance.receive("ec_launchers_in")
        assert msg.timestamp == TIMES[i]

        ids = imas.IDSFactory(TEST_DD_VERSION).ec_launchers()
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


# --- whole-trace mode: an '<ids>_in' port carrying an IDS -> its /time is exported ----

TRACE_YAML = f"""
dd_version: {TEST_DD_VERSION}
output:
  plasma_current:
    equilibrium/time_slice/global_quantities/ip:
      - {{to: 8.33e5, duration: 20}}
      - {{type: constant, duration: 20}}
      - {{duration: 25, to: 0}}
"""
# Same waveform as the per-slice test, but now interpolated onto a whole trace at once:
TRACE_TIMES = [1.0, 21.0, 50.0]
TRACE_IP = [8.33e5 / 20, 8.33e5, 8.33e5 * 15 / 25]

TRACE_YMMSL = """
ymmsl_version: v0.2

models:
  test_waveform_actor_trace:
    components:
      trace_generator:
        description: Emits a whole-trace equilibrium
        implementation: trace_generator
        ports:
          o_i: [output]
      waveform_actor:
        description: The actor under test
        implementation: waveform_actor
        ports:
          f_init: [equilibrium_in]
          o_f: [equilibrium_out]
      trace_validator:
        description: Validates the exported trace
        implementation: trace_validator
        ports:
          f_init: [equilibrium_in]

    conduits:
      trace_generator.output: waveform_actor.equilibrium_in
      waveform_actor.equilibrium_out: trace_validator.equilibrium_in

settings:
  waveform_actor.waveforms: {waveform_yaml}
"""


def trace_generator():
    instance = libmuscle.Instance({ymmsl.Operator.O_I: ["output"]})

    while instance.reuse_instance():
        # Send a whole-trace equilibrium; the actor only reads its /time and returns a
        # fresh equilibrium evaluated on it.
        eq = imas.IDSFactory(TEST_DD_VERSION).equilibrium()
        eq.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        eq.time = TRACE_TIMES
        instance.send("output", libmuscle.Message(TRACE_TIMES[0], data=eq.serialize()))


def trace_validator():
    instance = libmuscle.Instance({ymmsl.Operator.F_INIT: ["equilibrium_in"]})

    i = 0
    while instance.reuse_instance():
        msg = instance.receive("equilibrium_in")
        ids = imas.IDSFactory(TEST_DD_VERSION).equilibrium()
        ids.deserialize(msg.data)

        # A single message now carries the full trace interpolated on the input /time:
        assert np.array_equal(ids.time, TRACE_TIMES)
        assert len(ids.time_slice) == len(TRACE_TIMES)
        ip = [ts.global_quantities.ip for ts in ids.time_slice]
        assert np.allclose(ip, TRACE_IP)
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


# --- unit tests for _export_times ------------------------------------------------


class _Msg:
    """Minimal stand-in for a libmuscle Message (only the fields the helper reads)."""

    def __init__(self, data, timestamp=0.0):
        self.data = data
        self.timestamp = timestamp


def _eq_msg(homogeneous_time, time):
    eq = imas.IDSFactory(TEST_DD_VERSION).equilibrium()
    eq.ids_properties.homogeneous_time = homogeneous_time
    if time is not None:
        eq.time = time
    return _Msg(eq.serialize())


def test_heterogeneous_warns(caplog):
    """A heterogeneous input is still exported on, but warns."""
    msg = _eq_msg(imas.ids_defs.IDS_TIME_MODE_HETEROGENEOUS, TRACE_TIMES)
    with caplog.at_level("INFO"):
        times = _export_times(msg, "equilibrium_in", TEST_DD_VERSION)
    assert np.array_equal(times, TRACE_TIMES)
    assert "heterogeneous time mode" in caplog.text


def test_homogeneous_does_not_warn(caplog):
    msg = _eq_msg(imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS, TRACE_TIMES)
    with caplog.at_level("WARNING"):
        _export_times(msg, "equilibrium_in", TEST_DD_VERSION)
    assert "heterogeneous time mode" not in caplog.text


def test_missing_time_raises():
    msg = _eq_msg(imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS, None)
    with pytest.raises(RuntimeError, match="has no root /time"):
        _export_times(msg, "equilibrium_in", TEST_DD_VERSION)


def test_missing_data_raises():
    with pytest.raises(RuntimeError, match="nothing to take a time base from"):
        _export_times(_Msg(None), "equilibrium_in", TEST_DD_VERSION)


def test_invalid_port_name_raises():
    """The input port must be named '<ids>_in' for a valid IDS; anything else errors
    rather than silently falling back to some other mode."""
    msg = _eq_msg(imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS, TRACE_TIMES)
    with pytest.raises(RuntimeError, match="must be named '<ids>_in'"):
        _export_times(msg, "time_in", TEST_DD_VERSION)
