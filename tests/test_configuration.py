import pytest

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.waveform import Waveform


@pytest.fixture
def config():
    config = WaveformConfiguration()
    config.add_group("ec_launchers", [])
    config.add_group("beams", ["ec_launchers"])
    config.add_group("phase_angles", ["ec_launchers", "beams"])
    config.add_group("steering_angles", ["ec_launchers", "beams"])
    return config


def test_add_group(config):
    """Test if groups are added correctly  to the configuration."""
    assert config["ec_launchers"].name == "ec_launchers"
    assert config["ec_launchers"]["beams"].name == "beams"
    assert config["ec_launchers"]["beams"]["phase_angles"].name == "phase_angles"
    assert config["ec_launchers"]["beams"]["steering_angles"].name == "steering_angles"


def test_add_waveform(config):
    """Test if waveforms are added correctly to the configuration."""
    waveform1 = Waveform(name="waveform1")
    waveform2 = Waveform(name="waveform2")
    waveform3 = Waveform(name="waveform3")
    waveform4 = Waveform(name="waveform4")

    path1 = ["ec_launchers", "beams", "steering_angles"]
    path2 = ["ec_launchers"]
    path3_4 = ["ec_launchers", "beams", "phase_angles"]

    config.add_waveform(waveform1, path1)
    config.add_waveform(waveform2, path2)
    config.add_waveform(waveform3, path3_4)
    config.add_waveform(waveform4, path3_4)

    waveforms_path1 = config.traverse(path1).waveforms
    assert len(waveforms_path1) == 1
    assert waveforms_path1["waveform1"].name == "waveform1"

    waveforms_path2 = config.traverse(path2).waveforms
    assert len(waveforms_path2) == 1
    assert waveforms_path2["waveform2"].name == "waveform2"

    waveforms_path3_4 = config.traverse(path3_4).waveforms
    assert len(waveforms_path3_4) == 2
    assert waveforms_path3_4["waveform3"].name == "waveform3"
    assert waveforms_path3_4["waveform4"].name == "waveform4"

    assert len(config.traverse(["ec_launchers", "beams"]).waveforms) == 0

    # Waveforms cannot be stored at root level
    with pytest.raises(ValueError):
        config.add_waveform(waveform1, [])

    assert all(
        key in config.waveform_map
        for key in ["waveform1", "waveform2", "waveform3", "waveform4"]
    )


def test_add_waveform_duplicate(config):
    """Test if error is raised when waveform that already exists is added."""
    waveform1 = Waveform(name="waveform1")
    path1 = ["ec_launchers", "beams", "steering_angles"]
    path2 = ["ec_launchers"]
    config.add_waveform(waveform1, path1)
    with pytest.raises(ValueError):
        config.add_waveform(waveform1, path2)


def test_add_group_duplicate():
    """Test if error is raised when group that already exists at a path is added."""
    config = WaveformConfiguration()

    config.add_group("ec_launchers", [])
    with pytest.raises(ValueError):
        config.add_group("ec_launchers", [])

    config.add_group("beams", ["ec_launchers"])
    with pytest.raises(ValueError):
        config.add_group("beams", ["ec_launchers"])
