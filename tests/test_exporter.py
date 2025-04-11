import imas
import numpy as np

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
    exporter.to_ids(file_path)

    # FLT_1D
    with imas.DBEntry(file_path, "r") as dbentry:
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.time == times)
        assert np.all(ids.beam[0].phase.angle == 1e-3)
        assert np.all(ids.beam[1].phase.angle == 2)
        assert np.all(ids.beam[2].phase.angle == 3)
        assert np.all(ids.beam[3].power_launched.data == [1.1, 2.2, 3.3])

    # FLT_0D
    with imas.DBEntry(file_path, "r") as dbentry:
        ids = dbentry.get("equilibrium", autoconvert=False)
        assert np.all(ids.time == times)
        assert ids.time_slice[0].global_quantities.ip == 2
        assert ids.time_slice[1].global_quantities.ip == 3
        assert ids.time_slice[2].global_quantities.ip == 1
