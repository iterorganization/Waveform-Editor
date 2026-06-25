import imas
import numpy as np
import pytest

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.export.exporter import ConfigurationExporter


@pytest.fixture
def ec_launchers_md_uri(tmp_path):
    md_uri = f"{tmp_path}/md.nc"
    with imas.DBEntry(md_uri, "w", dd_version="4.0.0") as dbentry:
        ec = dbentry.factory.new("ec_launchers")
        ec.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_INDEPENDENT
        ec.beam.resize(4)
        ec.beam[0].name = "beam0"
        ec.beam[1].name = "beam1"
        ec.beam[2].name = "beam2"
        ec.beam[3].name = "beam3"
        dbentry.put(ec)
    return md_uri


def assert_ec_launchers_md(ec):
    assert ec.beam[0].name == "beam0"
    assert ec.beam[1].name == "beam1"
    assert ec.beam[2].name == "beam2"
    assert ec.beam[3].name == "beam3"


@pytest.fixture
def core_sources_md_uri(tmp_path):
    md_uri = f"{tmp_path}/md.nc"
    with imas.DBEntry(md_uri, "w", dd_version="4.0.0") as dbentry:
        cs = dbentry.factory.new("core_sources")
        cs.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_INDEPENDENT
        cs.source.resize(4)
        cs.source[0].identifier = "total"
        cs.source[1].identifier = "nbi"
        cs.source[2].identifier = "ec"
        cs.source[3].identifier = "lh"
        dbentry.put(cs)
    return md_uri


def assert_core_sources_md(cs):
    assert cs.source[0].identifier.name == "total"
    assert cs.source[1].identifier.name == "nbi"
    assert cs.source[2].identifier.name == "ec"
    assert cs.source[3].identifier.name == "lh"


def test_to_ids(tmp_path):
    """Check if to_ids fills the correct quantities."""

    yaml_str = """
    equilibrium:
      equilibrium/time_slice/global_quantities/ip:
      - {from: 2, to: 3, duration: 0.5}
      - {from: 3, to: 1, duration: 0.5}
    ec_launchers:
      phase_angles:
        ec_launchers/beam(1)/phase/angle: 1e-3
        ec_launchers/beam(2)/phase/angle: 2
        ec_launchers/beam(3)/phase/angle: 3
      power_launched:
        ec_launchers/beam(4)/power_launched/data:
        - {type: piecewise, time: [0, 0.5, 1], value: [1.1, 2.2, 3.3]}
    """
    file_path = f"{tmp_path}/test.nc"
    times = np.array([0, 0.5, 1])
    _export_ids(file_path, yaml_str, times)

    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        # FLT_1D
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.time == times)
        assert len(ids.beam) == 4
        assert np.array_equal(ids.beam[0].phase.angle, [1e-3] * 3)
        assert np.array_equal(ids.beam[1].phase.angle, [2] * 3)
        assert np.array_equal(ids.beam[2].phase.angle, [3] * 3)
        assert np.all(ids.beam[3].power_launched.data == [1.1, 2.2, 3.3])

        # FLT_0D
        ids = dbentry.get("equilibrium", autoconvert=False)
        assert np.all(ids.time == times)
        assert len(ids.time_slice) == len(times)
        assert ids.time_slice[0].global_quantities.ip == 2
        assert ids.time_slice[1].global_quantities.ip == 3
        assert ids.time_slice[2].global_quantities.ip == 1


def test_to_ids_inverted(tmp_path):
    """Check if to_ids fills the correct quantities, if the indices are in decreasing
    order."""

    yaml_str = """
    ec_launchers:
      power_launched:
        ec_launchers/beam(4)/power_launched/data:
        - {type: piecewise, time: [0, 0.5, 1], value: [1.1, 2.2, 3.3]}
      phase_angles:
        ec_launchers/beam(3)/phase/angle: 3
        ec_launchers/beam(2)/phase/angle: 2
        ec_launchers/beam(1)/phase/angle: 1e-3
    """
    file_path = f"{tmp_path}/test.nc"
    times = np.array([0, 0.5, 1])
    _export_ids(file_path, yaml_str, times)

    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        # FLT_1D
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.time == times)
        assert len(ids.beam) == 4
        assert np.array_equal(ids.beam[0].phase.angle, [1e-3] * 3)
        assert np.array_equal(ids.beam[1].phase.angle, [2] * 3)
        assert np.array_equal(ids.beam[2].phase.angle, [3] * 3)
        assert np.all(ids.beam[3].power_launched.data == [1.1, 2.2, 3.3])


def test_to_ids_python_notation(tmp_path):
    """Check if to_ids fills correctly using 0-based indexing."""
    yaml_str = """
    ec_launchers:
      ec_launchers/beam[2]/phase/angle: 5
    """
    file_path = f"{tmp_path}/test.nc"
    times = np.array([0, 0.5, 1])
    _export_ids(file_path, yaml_str, times)

    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.time == times)
        assert np.array_equal(ids.beam[2].phase.angle, [5] * 3)
        assert len(ids.beam) == 3


def test_to_ids_aos(tmp_path):
    """Check if to_ids fills correctly when a time dependent AoS appears together
    with another AoS."""

    yaml_str = """
    edge_profiles:
      # time dependent AoS before other AoS
      edge_profiles/profiles_1d/ion[4]/state[5]/z_max: [{from: 3, to: 5}]
    core_sources:
      # time dependent AoS after other AoS
      core_sources/source(5)/global_quantities/total_ion_power:
      - {from: 0, to: 2}
    """
    file_path = f"{tmp_path}/test.nc"
    times = np.array([0, 0.5, 1])
    _export_ids(file_path, yaml_str, times)

    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("edge_profiles", autoconvert=False)
        assert np.all(ids.time == times)
        assert len(ids.profiles_1d) == 3
        for i in range(len(times)):
            assert len(ids.profiles_1d[i].ion) == 5
            assert len(ids.profiles_1d[i].ion[4].state) == 6

        assert ids.profiles_1d[0].ion[4].state[5].z_max == 3
        assert ids.profiles_1d[1].ion[4].state[5].z_max == 4
        assert ids.profiles_1d[2].ion[4].state[5].z_max == 5

        ids = dbentry.get("core_sources", autoconvert=False)
        assert np.all(ids.time == times)
        assert len(ids.source) == 5
        assert len(ids.source[4].global_quantities) == len(times)
        assert ids.source[4].global_quantities[0].total_ion_power == 0
        assert ids.source[4].global_quantities[1].total_ion_power == 1
        assert ids.source[4].global_quantities[2].total_ion_power == 2


def test_export_with_md(tmp_path, ec_launchers_md_uri):
    """A whole-IDS import (`ec_launchers/*`) acts as a machine-description base: it is
    overlaid first, then explicit leaf waveforms override individual nodes."""
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {ec_launchers_md_uri}
    ec_launchers:
      ec_launchers/*:
        - {{ref: md}}
      ec_launchers/beam(2)/phase/angle: 1
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 4
        assert_ec_launchers_md(ids)
        assert np.array_equal(ids.beam[1].phase.angle, [1] * 3)


def test_export_full_slice_flt_1d(tmp_path):
    yaml_str = """
    ec_launchers:
      ec_launchers/beam(:)/phase/angle: 111
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 1
        assert np.array_equal(ids.beam[0].phase.angle, [111] * 3)


def test_export_full_slice_md_flt_1d(tmp_path, ec_launchers_md_uri):
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {ec_launchers_md_uri}
    ec_launchers:
      ec_launchers/*:
        - {{ref: md}}
      ec_launchers/beam(:)/phase/angle: 123
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 4
        assert_ec_launchers_md(ids)
        for i in range(0, 4):
            assert np.array_equal(ids.beam[i].phase.angle, [123] * 3)


def test_export_slice_flt_1d(tmp_path):
    yaml_str = """
    ec_launchers:
      ec_launchers/beam(2:3)/phase/angle: 111
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 3
        assert not ids.beam[0].phase.angle
        assert np.array_equal(ids.beam[1].phase.angle, [111] * 3)
        assert np.array_equal(ids.beam[2].phase.angle, [111] * 3)


def test_export_slice_md_flt_1d(tmp_path, ec_launchers_md_uri):
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {ec_launchers_md_uri}
    ec_launchers:
      ec_launchers/*:
        - {{ref: md}}
      ec_launchers/beam(2:3)/phase/angle: 123
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 4
        assert_ec_launchers_md(ids)
        assert not ids.beam[0].phase.angle
        assert np.array_equal(ids.beam[1].phase.angle, [123] * 3)
        assert np.array_equal(ids.beam[2].phase.angle, [123] * 3)
        assert not ids.beam[3].phase.angle


def test_export_half_slice_forward_flt_1d(tmp_path):
    yaml_str = """
    ec_launchers:
      ec_launchers/beam(3:)/phase/angle: 111
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 3
        assert not ids.beam[0].phase.angle
        assert not ids.beam[1].phase.angle
        assert np.array_equal(ids.beam[2].phase.angle, [111] * 3)


def test_export_half_slice_backward_flt_1d(tmp_path):
    yaml_str = """
    ec_launchers:
      ec_launchers/beam(:3)/phase/angle: 111
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 3
        for i in range(0, 3):
            assert np.array_equal(ids.beam[i].phase.angle, [111] * 3)


def test_export_half_slice_md_forward_flt_1d(tmp_path, ec_launchers_md_uri):
    """Load the yaml string into a waveform config and export to an IDS."""
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {ec_launchers_md_uri}
    ec_launchers:
      ec_launchers/*:
        - {{ref: md}}
      ec_launchers/beam(2:)/phase/angle: 123
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 4
        assert_ec_launchers_md(ids)
        assert not ids.beam[0].phase.angle
        for i in range(1, 4):
            assert np.array_equal(ids.beam[i].phase.angle, [123] * 3)


def test_export_half_slice_md_backward_flt_1d(tmp_path, ec_launchers_md_uri):
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {ec_launchers_md_uri}
    ec_launchers:
      ec_launchers/*:
        - {{ref: md}}
      ec_launchers/beam(:2)/phase/angle: 123
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 4
        assert_ec_launchers_md(ids)
        assert np.array_equal(ids.beam[0].phase.angle, [123] * 3)
        assert np.array_equal(ids.beam[1].phase.angle, [123] * 3)
        assert not ids.beam[2].phase.angle
        assert not ids.beam[3].phase.angle


def test_export_multiple_slices_flt_1d(tmp_path):
    yaml_str = """
    interferometer:
      interferometer/channel(2:3)/wavelength(:4)/phase_corrected/data: 15
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("interferometer", autoconvert=False)
        channels = ids.channel
        assert len(channels) == 3
        assert not channels[0].has_value
        assert len(channels[1].wavelength) == 4
        assert len(channels[2].wavelength) == 4
        for i in range(4):
            assert np.array_equal(
                channels[1].wavelength[i].phase_corrected.data, [15] * 3
            )
            assert np.array_equal(
                channels[2].wavelength[i].phase_corrected.data, [15] * 3
            )


def test_export_full_slice_flt_0d(tmp_path):
    yaml_str = """
    core_sources:
      core_sources/source(:)/global_quantities/power:
      - {type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("core_sources")
        assert len(ids.source) == 1
        assert len(ids.source[0].global_quantities) == len(times)
        for i in range(0, 3):
            assert ids.source[0].global_quantities[i].power == i + 1


def test_export_full_slice_md_flt_0d(tmp_path, core_sources_md_uri):
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {core_sources_md_uri}
    core_sources:
      core_sources/*:
        - {{ref: md}}
      core_sources/source(:)/global_quantities/power:
      - {{type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("core_sources")
        assert len(ids.source) == 4
        assert_core_sources_md(ids)
        for i in range(4):
            assert len(ids.source[i].global_quantities) == len(times)
            for j in range(3):
                assert ids.source[i].global_quantities[j].power == j + 1


def test_export_slice_flt_0d(tmp_path):
    yaml_str = """
    core_sources:
      core_sources/source(2:3)/global_quantities/power:
      - {type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("core_sources")
        assert len(ids.source) == 3
        assert not ids.source[0].has_value
        for i in range(1, 3):
            assert len(ids.source[i].global_quantities) == len(times)
            for j in range(3):
                assert ids.source[i].global_quantities[j].power == j + 1


def test_export_slice_md_flt_0d(tmp_path, core_sources_md_uri):
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {core_sources_md_uri}
    core_sources:
      core_sources/*:
        - {{ref: md}}
      core_sources/source(2:3)/global_quantities/power:
      - {{type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)

    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("core_sources")
        assert len(ids.source) == 4
        assert_core_sources_md(ids)

        assert not ids.source[0].global_quantities
        for i in range(1, 3):
            assert len(ids.source[i].global_quantities) == len(times)
            for j in range(3):
                assert ids.source[i].global_quantities[j].power == j + 1
        assert not ids.source[3].global_quantities


def test_export_half_slice_forward_flt_0d(tmp_path):
    yaml_str = """
    core_sources:
      core_sources/source(3:)/global_quantities/power:
      - {type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("core_sources")
        assert len(ids.source) == 3
        assert not ids.source[0].has_value
        assert not ids.source[1].has_value
        assert len(ids.source[2].global_quantities) == len(times)
        for j in range(3):
            assert ids.source[2].global_quantities[j].power == j + 1


def test_export_half_slice_backward_flt_0d(tmp_path):
    yaml_str = """
    core_sources:
      core_sources/source(:3)/global_quantities/power:
      - {type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("core_sources")
        assert len(ids.source) == 3
        for i in range(3):
            assert len(ids.source[i].global_quantities) == len(times)
            for j in range(3):
                assert ids.source[i].global_quantities[j].power == j + 1


def test_export_half_slice_md_forward_flt_0d(tmp_path, core_sources_md_uri):
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {core_sources_md_uri}
    core_sources:
      core_sources/*:
        - {{ref: md}}
      core_sources/source(2:)/global_quantities/power:
      - {{type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("core_sources")
        assert len(ids.source) == 4
        assert_core_sources_md(ids)
        assert not ids.source[0].global_quantities
        for i in range(1, 4):
            assert len(ids.source[i].global_quantities) == len(times)
            for j in range(3):
                assert ids.source[i].global_quantities[j].power == j + 1


def test_export_half_slice_md_backward_flt_0d(tmp_path, core_sources_md_uri):
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      imports:
        md: {core_sources_md_uri}
    core_sources:
      core_sources/*:
        - {{ref: md}}
      core_sources/source(:2)/global_quantities/power:
      - {{type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("core_sources")
        assert len(ids.source) == 4
        assert_core_sources_md(ids)
        for i in range(2):
            assert len(ids.source[i].global_quantities) == len(times)
            for j in range(3):
                assert ids.source[i].global_quantities[j].power == j + 1
        assert not ids.source[2].global_quantities
        assert not ids.source[3].global_quantities


def test_export_multiple_slices_flt_0d(tmp_path):
    yaml_str = """
    distributions:
      distributions/distribution(2:3)/global_quantities/collisions/ion(3:)/state(:5)/z_max:
      - {type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    _assert_distributions_ids(uri)


def test_export_multiple_slices_flt_0d_python_notation(tmp_path):
    yaml_str = """
    distributions:
      distributions/distribution[1:3]/global_quantities/collisions/ion[2:]/state[:5]/z_max:
      - {type: piecewise, time: [0, 0.5, 1], value: [1,2,3]}
    """
    uri = f"{tmp_path}/test_db.nc"
    times = np.array([0, 0.5, 1.0])
    _export_ids(uri, yaml_str, times)
    _assert_distributions_ids(uri)


def _assert_distributions_ids(uri):
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("distributions", autoconvert=False)
        distributions = ids.distribution
        assert len(distributions) == 3
        assert not distributions[0].has_value
        for i in range(1, 3):
            assert len(distributions[i].global_quantities) == 3
            for j in range(3):
                ions = distributions[i].global_quantities[j].collisions.ion
                assert len(ions) == 3
                assert len(ions[2].state) == 5
                for k in range(5):
                    assert (
                        distributions[i]
                        .global_quantities[j]
                        .collisions.ion[2]
                        .state[k]
                        .z_max
                        == j + 1
                    )


def test_export_ordering(tmp_path):
    yaml_str = """
    ec_launchers:
      ec_launchers/beam(:)/phase/angle: 111
      ec_launchers/beam(4)/power_launched/data:
      - {type: piecewise, time: [0, 0.5, 1], value: [1.1, 2.2, 3.3]}
    """
    uri = f"{tmp_path}/test_db.nc"
    _export_ids(uri, yaml_str, np.array([0, 0.5, 1.0]))
    _assert_ordering(uri)

    yaml_str2 = """
    ec_launchers:
      ec_launchers/beam(4)/power_launched/data:
      - {type: piecewise, time: [0, 0.5, 1], value: [1.1, 2.2, 3.3]}
      ec_launchers/beam(:)/phase/angle: 111
    """
    uri2 = f"{tmp_path}/test_db2.nc"
    _export_ids(uri2, yaml_str2, np.array([0, 0.5, 1.0]))
    _assert_ordering(uri2)


def _assert_ordering(uri):
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 4
        for i in range(0, 4):
            assert np.array_equal(ids.beam[i].phase.angle, [111] * 3)
        assert np.all(ids.beam[3].power_launched.data == [1.1, 2.2, 3.3])


def _export_ids(file_path, yaml_str, times):
    """Load the yaml string into a waveform config and export to an IDS."""
    config = WaveformConfiguration()
    config.load_yaml(yaml_str)
    exporter = ConfigurationExporter(config, times)
    exporter.to_ids(file_path)


def test_increasing_times():
    config = WaveformConfiguration()
    # This is fine:
    ConfigurationExporter(config, np.linspace(0, 1, 5))
    ConfigurationExporter(config, np.array([0]))

    with pytest.raises(ValueError):
        ConfigurationExporter(config, np.linspace(1, 0, 5))
    with pytest.raises(ValueError):
        ConfigurationExporter(config, np.array([0, 0, 1]))
    with pytest.raises(ValueError):
        ConfigurationExporter(config, np.array([0, 2, 1]))


def test_export_constant(tmp_path):
    """Check if constant waveforms are exported correctly"""

    yaml_str = """
    ec_launchers:
      ec_launchers/beam(1)/phase/angle: 1
      ec_launchers/beam(2)/phase/angle: 2.2
      ec_launchers/beam(3)/phase/angle: 3.3e3
    """
    file_path = f"{tmp_path}/test.nc"
    times = np.array([0, 1, 2])
    _export_ids(file_path, yaml_str, times)
    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.array_equal(ids.beam[0].phase.angle, [1] * 3)
        assert np.array_equal(ids.beam[1].phase.angle, [2.2] * 3)
        assert np.array_equal(ids.beam[2].phase.angle, [3.3e3] * 3)


def test_example_yaml(tmp_path):
    """Test for an example YAML file if all IDSs are correctly filled."""

    file_path = f"{tmp_path}/test.nc"
    with open("tests/test_yaml/example.yaml") as file:
        yaml_str = file.read()
    times = np.array([0, 100, 200, 300, 400, 500])
    values = np.array([0, 1e5, 1e5, 1e5, 1e5, 0])
    _export_ids(file_path, yaml_str, times)

    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        core_profiles = dbentry.get("core_profiles", autoconvert=False)
        equilibrium = dbentry.get("equilibrium", autoconvert=False)
        ic_antennas = dbentry.get("ic_antennas", autoconvert=False)
        pellets = dbentry.get("pellets", autoconvert=False)
        ec_launchers = dbentry.get("ec_launchers", autoconvert=False)
        gas_injection = dbentry.get("gas_injection", autoconvert=False)
        interferometer = dbentry.get("interferometer", autoconvert=False)
        nbi = dbentry.get("nbi", autoconvert=False)

    assert np.all(core_profiles.time == times)
    assert np.all(equilibrium.time == times)
    assert np.all(ic_antennas.time == times)
    assert np.all(pellets.time == times)
    assert np.all(ec_launchers.time == times)
    assert np.all(gas_injection.time == times)
    assert np.all(interferometer.time == times)
    assert np.all(nbi.time == times)

    assert np.all(core_profiles.global_quantities.ip == values)
    assert np.all(core_profiles.global_quantities.z_eff_resistive == values)
    assert np.all(core_profiles.vacuum_toroidal_field.b0 == values)

    assert np.all(equilibrium.vacuum_toroidal_field.b0 == values)
    for i, ts in enumerate(equilibrium.time_slice):
        assert ts.global_quantities.ip == values[i]

    assert np.all(ic_antennas.antenna[0].frequency.data == 40e6)
    assert np.all(ic_antennas.antenna[0].power_launched.data == values)
    assert np.all(ic_antennas.antenna[0].module[0].strap[0].phase.data == 1.5708)

    for i, ts in enumerate(pellets.time_slice):
        assert ts.pellet[0].velocity_initial == values[i]

    assert np.all(ec_launchers.beam[0].power_launched.data == values)
    assert np.all(ec_launchers.beam[0].frequency.data == 170e9)
    assert np.all(ec_launchers.beam[0].steering_angle_pol == values)
    assert np.all(ec_launchers.beam[0].steering_angle_tor == values)
    assert np.all(ec_launchers.beam[0].phase.angle == values)

    assert np.all(gas_injection.valve[0].flow_rate.data == values)
    assert np.all(gas_injection.valve[0].electron_rate.data == values)
    assert np.all(gas_injection.pipe[0].flow_rate.data == values)

    assert np.all(interferometer.channel[0].n_e_line.data == values)

    assert np.all(
        nbi.unit[0].power_launched.data == 16.5e6 * (values**2.5) / (870e3**2.5)
    )
    assert np.all(nbi.unit[0].energy.data == values)


@pytest.fixture
def core_sources_ext_uri(tmp_path):
    """An external, time-dependent core_sources to import from. Its single source has
    only identifier.index set (no identifier.name), so the config assigns the name."""
    uri = f"imas:hdf5?path={tmp_path}/ext"
    with imas.DBEntry(uri, "w", dd_version="4.0.0") as dbentry:
        cs = dbentry.factory.new("core_sources")
        cs.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        cs.time = [0.0, 1.0, 2.0]
        cs.source.resize(1)
        cs.source[0].identifier.index = 1
        cs.source[0].profiles_1d.resize(3)
        for t in range(3):
            cs.source[0].profiles_1d[t].grid.rho_tor_norm = [0.0, 0.5, 1.0]
            cs.source[0].profiles_1d[t].electrons.energy = [t * 10.0] * 3
        dbentry.put(cs)
    return uri


def test_import_scalar(core_sources_ext_uri):
    """An import reads its (resampled) value per variable from a named entry at the same
    path; a {value: <string>} constant assigns a static field (e.g. a name)."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{core_sources_ext_uri}"
Heating:
  core_sources/source(1)/profiles_1d/electrons/energy:
    - {{type: reference, ref: ext}}
  core_sources/source(1)/identifier/name:
    - {{value: ec}}
"""
    )
    times = np.array([0.0, 1.0, 2.0])
    cs = ConfigurationExporter(config, times).to_ids_dict()["core_sources"]

    # a {value: <string>} constant names the (1-based) first source:
    assert str(cs.source[0].identifier.name) == "ec"
    # the profile was read from the reference and resampled onto /time:
    assert np.allclose(
        [cs.source[0].profiles_1d[t].electrons.energy[0] for t in range(3)],
        [0.0, 10.0, 20.0],
    )
    # only the referenced node was imported, not its siblings:
    assert len(cs.source[0].profiles_1d[0].grid.rho_tor_norm) == 0


@pytest.fixture
def equilibrium_ext_uri(tmp_path):
    """An external equilibrium with a scalar ip(t) = 0, 10, 20 at t = 0, 1, 2."""
    uri = f"imas:hdf5?path={tmp_path}/eq"
    with imas.DBEntry(uri, "w", dd_version="4.0.0") as dbentry:
        eq = dbentry.factory.new("equilibrium")
        eq.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        eq.time = [0.0, 1.0, 2.0]
        eq.time_slice.resize(3)
        for t in range(3):
            eq.time_slice[t].global_quantities.ip = t * 10.0
        dbentry.put(eq)
    return uri


def test_import_composite(equilibrium_ext_uri):
    """A scalar waveform mixing an analytic and an import segment: each fills its
    [start, end] window. Imports may be combined with analytic segments only for 0D."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{equilibrium_ext_uri}"
Plasma current:
  equilibrium/time_slice/global_quantities/ip:
    - {{type: constant, value: -1.0, duration: 1}}
    - {{ref: ext, duration: 1}}
"""
    )
    times = np.array([0.0, 2.0])
    eq = ConfigurationExporter(config, times).to_ids_dict()["equilibrium"]

    # [0, 1] s: analytic constant -1; [1, 2] s: reference ip (20 at t=2)
    assert eq.time_slice[0].global_quantities.ip == -1.0
    assert eq.time_slice[1].global_quantities.ip == 20.0


def test_import_wildcard(core_sources_ext_uri):
    """A `*` after a prefix imports every filled leaf of that subtree from the entry."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{core_sources_ext_uri}"
Heating:
  core_sources/source(1)/profiles_1d/*:
    - {{ref: ext}}
"""
    )
    times = np.array([0.0, 1.0, 2.0])
    cs = ConfigurationExporter(config, times).to_ids_dict()["core_sources"]

    # both leaves under profiles_1d were imported across all three slices:
    assert len(cs.source[0].profiles_1d) == 3
    assert np.allclose(
        [cs.source[0].profiles_1d[t].electrons.energy[0] for t in range(3)],
        [0.0, 10.0, 20.0],
    )
    assert np.allclose(cs.source[0].profiles_1d[0].grid.rho_tor_norm, [0.0, 0.5, 1.0])


@pytest.fixture
def core_sources_multi_ext_uri(tmp_path):
    """An external core_sources with two sources; source(s) has electrons.energy
    offset by 100*s so each source is distinguishable after import."""
    uri = f"imas:hdf5?path={tmp_path}/multi"
    with imas.DBEntry(uri, "w", dd_version="4.0.0") as dbentry:
        cs = dbentry.factory.new("core_sources")
        cs.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        cs.time = [0.0, 1.0, 2.0]
        cs.source.resize(2)
        for s in range(2):
            cs.source[s].profiles_1d.resize(3)
            for t in range(3):
                cs.source[s].profiles_1d[t].grid.rho_tor_norm = [0.0, 0.5, 1.0]
                cs.source[s].profiles_1d[t].electrons.energy = [100 * s + t * 10.0] * 3
        dbentry.put(cs)
    return uri


def test_import_index_wildcard(core_sources_multi_ext_uri):
    """A `(*)` index wildcard imports the leaf for every element of that array of
    structure in the source (here: the same leaf across all sources)."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{core_sources_multi_ext_uri}"
Heating:
  core_sources/source(*)/profiles_1d/electrons/energy:
    - {{ref: ext}}
"""
    )
    times = np.array([0.0, 1.0, 2.0])
    cs = ConfigurationExporter(config, times).to_ids_dict()["core_sources"]

    # both sources were imported, each with its own offset across all slices:
    assert len(cs.source) == 2
    for s in range(2):
        assert np.allclose(
            [cs.source[s].profiles_1d[t].electrons.energy[0] for t in range(3)],
            [100 * s + t * 10.0 for t in range(3)],
        )


@pytest.fixture
def core_sources_ions_ext_uri(tmp_path):
    """An external core_sources with two sources, each with two ions; ion z_ion encodes
    its (source, ion) indices as 10*source + ion so every combination is distinguishable
    after a two-dimensional wildcard import."""
    uri = f"imas:hdf5?path={tmp_path}/ions"
    with imas.DBEntry(uri, "w", dd_version="4.0.0") as dbentry:
        cs = dbentry.factory.new("core_sources")
        cs.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        cs.time = [0.0, 1.0]
        cs.source.resize(2)
        for s in range(2):
            cs.source[s].profiles_1d.resize(2)
            for t in range(2):
                cs.source[s].profiles_1d[t].ion.resize(2)
                for i in range(2):
                    cs.source[s].profiles_1d[t].ion[i].z_ion = 10.0 * s + i
        dbentry.put(cs)
    return uri


def test_import_index_wildcard_multi(core_sources_ions_ext_uri):
    """Multiple `(*)` index wildcards expand over every combination (here sources x
    ions), supporting higher-dimensional imports."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{core_sources_ions_ext_uri}"
Heating:
  core_sources/source(*)/profiles_1d/ion(*)/z_ion:
    - {{ref: ext}}
"""
    )
    times = np.array([0.0, 1.0])
    cs = ConfigurationExporter(config, times).to_ids_dict()["core_sources"]

    assert len(cs.source) == 2
    for s in range(2):
        assert len(cs.source[s].profiles_1d[0].ion) == 2
        for i in range(2):
            for t in range(2):
                assert cs.source[s].profiles_1d[t].ion[i].z_ion == 10.0 * s + i


@pytest.fixture
def core_sources_varying_ions_uri(tmp_path):
    """A core_sources whose ion array of structure varies in size across time slices
    (2 ions at t=0, 3 ions at t=1) -- a legal but wildcard-incompatible source."""
    uri = f"imas:hdf5?path={tmp_path}/varying"
    with imas.DBEntry(uri, "w", dd_version="4.0.0") as dbentry:
        cs = dbentry.factory.new("core_sources")
        cs.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        cs.time = [0.0, 1.0]
        cs.source.resize(1)
        cs.source[0].profiles_1d.resize(2)
        for t, n_ions in enumerate((2, 3)):
            cs.source[0].profiles_1d[t].ion.resize(n_ions)
            for i in range(n_ions):
                cs.source[0].profiles_1d[t].ion[i].z_ion = float(i)
        dbentry.put(cs)
    return uri


def test_import_index_wildcard_varying_in_time_raises(core_sources_varying_ions_uri):
    """A `(*)` over an array of structure whose size varies in time raises a clear
    error instead of silently importing only some elements."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{core_sources_varying_ions_uri}"
Heating:
  core_sources/source(1)/profiles_1d/ion(*)/z_ion:
    - {{ref: ext}}
"""
    )
    with pytest.raises(RuntimeError, match="varies across a time-dependent parent"):
        ConfigurationExporter(config, np.array([0.0, 1.0])).to_ids_dict()


def test_import_time_offset(core_sources_ext_uri):
    """`time_offset` shifts the time at which the import is sampled."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{core_sources_ext_uri}"
Heating:
  core_sources/source(1)/profiles_1d/electrons/energy:
    - {{type: reference, ref: ext, time_offset: 1.0}}
"""
    )
    times = np.array([0.0, 1.0])
    cs = ConfigurationExporter(config, times).to_ids_dict()["core_sources"]

    # sampled at t+1 (CLOSEST): export t=0 -> ext t=1 (10), export t=1 -> ext t=2 (20)
    assert np.allclose(
        [cs.source[0].profiles_1d[t].electrons.energy[0] for t in range(2)],
        [10.0, 20.0],
    )


def test_import_interp_linear(equilibrium_ext_uri):
    """`interp: linear` interpolates between the source time slices instead of snapping
    to the closest one."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{equilibrium_ext_uri}"
Plasma current:
  equilibrium/time_slice/global_quantities/ip:
    - {{ref: ext, interp: linear}}
"""
    )
    times = np.array([0.5, 1.5])
    eq = ConfigurationExporter(config, times).to_ids_dict()["equilibrium"]

    # ip is 0, 10, 20 at t = 0, 1, 2 -> linear interpolation gives 5 and 15:
    assert eq.time_slice[0].global_quantities.ip == 5.0
    assert eq.time_slice[1].global_quantities.ip == 15.0


def test_import_missing_entry_errors(core_sources_ext_uri):
    """Referring to an import name that is not declared raises, rather than silently
    producing an empty IDS."""
    config = WaveformConfiguration()
    config.load_yaml(
        """
globals:
  dd_version: 4.0.0
Heating:
  core_sources/source(1)/profiles_1d/electrons/energy:
    - {ref: does_not_exist}
"""
    )
    with pytest.raises(KeyError):
        ConfigurationExporter(config, np.array([0.0, 1.0])).to_ids_dict()


def test_import_port_overlay():
    """A `{port: <name>}` import reads an IDS supplied at run time (as the MUSCLE3 actor
    does); a whole-IDS import overlays it, then explicit leaves override."""
    received = imas.IDSFactory("4.0.0").new("equilibrium")
    received.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
    received.time = [0.0, 1.0]
    received.time_slice.resize(2)
    received.vacuum_toroidal_field.r0 = 6.2
    for t in range(2):
        received.time_slice[t].global_quantities.ip = 100.0

    config = WaveformConfiguration()
    config.load_yaml(
        """
globals:
  dd_version: 4.0.0
  imports:
    live: {port: equilibrium_in}
Plasma:
  equilibrium/*:
    - {ref: live}
  equilibrium/time_slice/global_quantities/ip:
    - {type: constant, value: 5.0}
"""
    )
    times = np.array([0.0, 1.0])
    exporter = ConfigurationExporter(
        config, times, received_idss={"equilibrium_in": received}
    )
    eq = exporter.to_ids_dict()["equilibrium"]

    # overlaid base field survived, while ip was overridden by the explicit waveform:
    assert eq.vacuum_toroidal_field.r0 == 6.2
    assert eq.time_slice[0].global_quantities.ip == 5.0


def test_scalar_import_resolves_in_waveform(equilibrium_ext_uri):
    """The scalar import value is produced by the waveform itself (get_value), not the
    exporter: the editor/CSV path resolves it directly via the import resolver."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{equilibrium_ext_uri}"
Plasma current:
  equilibrium/time_slice/global_quantities/ip:
    - {{ref: ext, interp: linear}}
"""
    )
    waveform = config["equilibrium/time_slice/global_quantities/ip"]
    times = np.array([0.5, 1.5])
    _, values = waveform.get_value(times)
    # ip is 0, 10, 20 at t = 0, 1, 2 -> linear interpolation gives 5 and 15:
    assert np.allclose(values, [5.0, 15.0])


def test_scalar_import_raw_in_editor(equilibrium_ext_uri):
    """With no time array (the editor plot), a lone import returns the raw source
    samples on the source's own time base -- not resampled onto a foreign grid."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    ext: "{equilibrium_ext_uri}"
Plasma current:
  equilibrium/time_slice/global_quantities/ip:
    - {{ref: ext}}
"""
    )
    waveform = config["equilibrium/time_slice/global_quantities/ip"]
    times, values = waveform.get_value()
    # the source's own samples: ip = 0, 10, 20 at t = 0, 1, 2
    assert np.allclose(times, [0.0, 1.0, 2.0])
    assert np.allclose(values, [0.0, 10.0, 20.0])


@pytest.fixture
def machine_ext_uri(tmp_path):
    """An external entry with two filled IDSs, for a whole-entry (root `*`) import: a
    homogeneous equilibrium with ip(t) and a time-independent ec_launchers."""
    uri = f"imas:hdf5?path={tmp_path}/machine"
    with imas.DBEntry(uri, "w", dd_version="4.0.0") as dbentry:
        eq = dbentry.factory.new("equilibrium")
        eq.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        eq.time = [0.0, 1.0, 2.0]
        eq.time_slice.resize(3)
        for t in range(3):
            eq.time_slice[t].global_quantities.ip = t * 10.0
        dbentry.put(eq)

        ec = dbentry.factory.new("ec_launchers")
        ec.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_INDEPENDENT
        ec.beam.resize(2)
        ec.beam[0].name = "beam0"
        ec.beam[1].name = "beam1"
        dbentry.put(ec)
    return uri


def test_root_import(machine_ext_uri):
    """A root `*` import overlays every IDS the source provides, each as a whole-IDS
    overlay base; explicit leaf waveforms still override afterwards."""
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    machine: "{machine_ext_uri}"
Machine:
  '*':
    - {{ref: machine}}
  equilibrium/time_slice/global_quantities/ip:
    - {{type: constant, value: 5.0}}
"""
    )
    times = np.array([0.0, 1.0, 2.0])
    idss = ConfigurationExporter(config, times).to_ids_dict()

    # both filled IDSs of the entry were overlaid:
    assert set(idss) == {"equilibrium", "ec_launchers"}
    assert [str(b.name) for b in idss["ec_launchers"].beam] == ["beam0", "beam1"]
    # the explicit ip waveform overrode the overlaid equilibrium values:
    assert np.allclose(
        [idss["equilibrium"].time_slice[t].global_quantities.ip for t in range(3)],
        [5.0, 5.0, 5.0],
    )


@pytest.fixture
def two_equilibria(tmp_path):
    """Two external equilibria for overlay-precedence tests: 'a' has ip(t) = 0,10,20 and
    r0 = 6.2; 'b' has a constant ip = 100 and r0 = 9.9."""
    a = f"imas:hdf5?path={tmp_path}/a"
    b = f"imas:hdf5?path={tmp_path}/b"
    for uri, const_ip, r0 in ((a, None, 6.2), (b, 100.0, 9.9)):
        with imas.DBEntry(uri, "w", dd_version="4.0.0") as dbentry:
            eq = dbentry.factory.new("equilibrium")
            eq.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
            eq.time = [0.0, 1.0, 2.0]
            eq.vacuum_toroidal_field.r0 = r0
            eq.time_slice.resize(3)
            for t in range(3):
                eq.time_slice[t].global_quantities.ip = (
                    const_ip if const_ip is not None else t * 10.0
                )
            dbentry.put(eq)
    return a, b


def test_multiple_root_imports(two_equilibria):
    """A root `*` may list several sources; they overlay in listed order, so the last
    wins at a shared leaf (equal specificity)."""
    a, b = two_equilibria
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    a: "{a}"
    b: "{b}"
Machine:
  '*':
    - {{ref: a}}
    - {{ref: b}}
"""
    )
    times = np.array([0.0, 1.0, 2.0])
    eq = ConfigurationExporter(config, times).to_ids_dict()["equilibrium"]

    # 'b' is listed last, so its values win:
    assert eq.vacuum_toroidal_field.r0 == 9.9
    assert np.allclose(
        [eq.time_slice[t].global_quantities.ip for t in range(3)], [100.0, 100.0, 100.0]
    )


def test_specificity_beats_order(two_equilibria):
    """A more specific overlay wins over a broader one regardless of listing order: the
    broad `equilibrium/*` is listed last but applied first, so the narrower
    `equilibrium/vacuum_toroidal_field/*` still wins for r0."""
    a, b = two_equilibria
    config = WaveformConfiguration()
    config.load_yaml(
        f"""
globals:
  dd_version: 4.0.0
  imports:
    a: "{a}"
    b: "{b}"
Machine:
  equilibrium/vacuum_toroidal_field/*:
    - {{ref: b}}
  equilibrium/*:
    - {{ref: a}}
"""
    )
    times = np.array([0.0, 1.0, 2.0])
    eq = ConfigurationExporter(config, times).to_ids_dict()["equilibrium"]

    # r0 from the more specific 'b' subtree, ip from the broad 'a' whole-IDS import:
    assert eq.vacuum_toroidal_field.r0 == 9.9
    assert np.allclose(
        [eq.time_slice[t].global_quantities.ip for t in range(3)], [0.0, 10.0, 20.0]
    )
