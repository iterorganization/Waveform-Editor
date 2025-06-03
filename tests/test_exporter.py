import imas
import numpy as np
import pytest

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.exporter import ConfigurationExporter


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
    """Test export if machine description is provided."""
    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      machine_description: 
        ec_launchers: {ec_launchers_md_uri}
    ec_launchers:
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
      machine_description: 
        ec_launchers: {ec_launchers_md_uri}
    ec_launchers:
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
      machine_description: 
        ec_launchers: {ec_launchers_md_uri}
    ec_launchers:
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
      machine_description: 
        ec_launchers: {ec_launchers_md_uri}
    ec_launchers:
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
      machine_description: 
        ec_launchers: {ec_launchers_md_uri}
    ec_launchers:
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
      machine_description: 
        core_sources: {core_sources_md_uri}
    core_sources:
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
      machine_description: 
        core_sources: {core_sources_md_uri}
    core_sources:
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
      machine_description: 
        core_sources: {core_sources_md_uri}
    core_sources:
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
      machine_description: 
        core_sources: {core_sources_md_uri}
    core_sources:
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
    config.dd_version = "4.0.0"
    config.parser.load_yaml(yaml_str)
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
