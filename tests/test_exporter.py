import imas
import numpy as np
import pytest

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.exporter import ConfigurationExporter


def test_to_ids(tmp_path):
    """Check if to_ids fills the correct quantities."""

    yaml_str = """
    equilibrium:
      equilibrium/time_slice/global_quantities/ip:
      - {from: 2, to: 3, duration: 0.5} 
      - {from: 3, to: 1, duration: 0.5} 
    ec_launchers:
      phase_angles:
        ec_launchers/beam(1)/phase/angle/data: 1e-3
        ec_launchers/beam(2)/phase/angle/data: 2
        ec_launchers/beam(3)/phase/angle/data: 3
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
        assert np.all(ids.beam[0].phase.angle == 1e-3)
        assert np.all(ids.beam[1].phase.angle == 2)
        assert np.all(ids.beam[2].phase.angle == 3)
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
        ec_launchers/beam(3)/phase/angle/data: 3
        ec_launchers/beam(2)/phase/angle/data: 2
        ec_launchers/beam(1)/phase/angle/data: 1e-3
    """
    file_path = f"{tmp_path}/test.nc"
    times = np.array([0, 0.5, 1])
    _export_ids(file_path, yaml_str, times)

    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        # FLT_1D
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.time == times)
        assert len(ids.beam) == 4
        assert np.all(ids.beam[0].phase.angle == 1e-3)
        assert np.all(ids.beam[1].phase.angle == 2)
        assert np.all(ids.beam[2].phase.angle == 3)
        assert np.all(ids.beam[3].power_launched.data == [1.1, 2.2, 3.3])


def test_to_ids_signal_flt_1d(tmp_path):
    """Check if to_ids raises error when filling a 'signal_flt_1d' structure."""

    yaml_str = """
    ec_launchers:
      ec_launchers/beam(1)/frequency: 1e5
    """
    file_path = f"{tmp_path}/test.nc"
    times = np.array([0, 0.5, 1])
    with pytest.raises(ValueError):
        _export_ids(file_path, yaml_str, times)


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
        assert np.all(ids.beam[2].phase.angle == 5)
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


def test_export_with_md(tmp_path):
    """Test export if machine description is provided."""
    # Create dummy machine description
    md_uri = f"{tmp_path}/md.nc"
    with imas.DBEntry(md_uri, "w", dd_version="4.0.0") as md_dbentry:
        md = md_dbentry.factory.new("ec_launchers")
        md.ids_properties.homogeneous_time = imas.ids_defs.IDS_TIME_MODE_INDEPENDENT
        md.beam.resize(3)
        md.beam[0].name = "beam0"
        md.beam[1].name = "beam1"
        md.beam[2].name = "beam2"
        md_dbentry.put(md)

    yaml_str = f"""
    globals:
      dd_version: 4.0.0
      machine_description: {tmp_path}/md.nc
    ec_launchers:
      ec_launchers/beam(2)/phase/angle: 1
    """
    config = WaveformConfiguration()
    config.load_yaml(yaml_str)
    uri = f"{tmp_path}/test_db.nc"
    config.export(np.array([0, 0.5, 1.0]), uri=uri)
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers")
        assert len(ids.beam) == 3
        assert ids.beam[0].name == "beam0"
        assert ids.beam[1].name == "beam1"
        assert ids.beam[2].name == "beam2"
        assert np.all(ids.beam[1].phase.angle == 1)


def _export_ids(file_path, yaml_str, times):
    """Load the yaml string into a waveform config and export to an IDS."""
    config = WaveformConfiguration()
    config.parser.load_yaml(yaml_str)
    exporter = ConfigurationExporter(config, times)
    exporter.to_ids(file_path, dd_version="4.0.0")
