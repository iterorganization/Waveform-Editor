import imas
import numpy as np

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.exporter import ConfigurationExporter


def test_to_ids(tmp_path):
    """Check if to_ids fills the correct quantities."""

    yaml_str = """
    core_sources:
      core_sources/source(5)/global_quantities/total_ion_power:
      - {from: 0, to: 2} 
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
        ec_launchers/beam(4)/power_launched:
        - {type: piecewise, time: [0, 0.5, 1], value: [1.1, 2.2, 3.3]}
    """
    config = WaveformConfiguration()
    config.load_yaml(yaml_str)
    times = np.array([0, 0.5, 1])
    exporter = ConfigurationExporter(config, times)
    file_path = f"{tmp_path}/test.nc"
    exporter.to_ids(file_path, dd_version="4.0.0")

    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        # FLT_1D
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.time == times)
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

        ids = dbentry.get("core_sources", autoconvert=False)
        assert np.all(ids.time == times)
        assert len(ids.source) == 5
        assert len(ids.source[4].global_quantities) == len(times)
        assert ids.source[4].global_quantities[0].total_ion_power == 0
        assert ids.source[4].global_quantities[1].total_ion_power == 1
        assert ids.source[4].global_quantities[2].total_ion_power == 2


def test_to_ids_python_notation(tmp_path):
    """Check if to_ids fills correctly using 0-based indexing."""
    yaml_str = """
    ec_launchers:
      ec_launchers/beam[2]/phase/angle: 5
    """
    config = WaveformConfiguration()
    config.load_yaml(yaml_str)
    times = np.array([0, 0.5, 1])
    exporter = ConfigurationExporter(config, times)
    file_path = f"{tmp_path}/test.nc"
    exporter.to_ids(file_path, dd_version="4.0.0")

    with imas.DBEntry(file_path, "r", dd_version="4.0.0") as dbentry:
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.time == times)
        assert np.all(ids.beam[2].phase.angle == 5)
        assert len(ids.beam) == 3
