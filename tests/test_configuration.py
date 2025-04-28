from textwrap import dedent

import pytest

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency
from waveform_editor.waveform import Waveform
from waveform_editor.yaml_parser import YamlParser


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
    waveform1 = Waveform(name="waveform/1")
    waveform2 = Waveform(name="waveform/2")
    waveform3 = Waveform(name="waveform/3")
    waveform4 = Waveform(name="waveform/4")

    path1 = ["ec_launchers", "beams", "steering_angles"]
    path2 = ["ec_launchers"]
    path3_4 = ["ec_launchers", "beams", "phase_angles"]

    config.add_waveform(waveform1, path1)
    config.add_waveform(waveform2, path2)
    config.add_waveform(waveform3, path3_4)
    config.add_waveform(waveform4, path3_4)

    waveforms_path1 = config.traverse(path1).waveforms
    assert len(waveforms_path1) == 1
    assert waveforms_path1["waveform/1"] == waveform1

    waveforms_path2 = config.traverse(path2).waveforms
    assert len(waveforms_path2) == 1
    assert waveforms_path2["waveform/2"] == waveform2

    waveforms_path3_4 = config.traverse(path3_4).waveforms
    assert len(waveforms_path3_4) == 2
    assert waveforms_path3_4["waveform/3"] == waveform3
    assert waveforms_path3_4["waveform/4"] == waveform4

    assert len(config.traverse(["ec_launchers", "beams"]).waveforms) == 0

    # Waveforms cannot be stored at root level
    with pytest.raises(ValueError):
        config.add_waveform(waveform1, [])

    # Check if all waveforms are in map
    assert set(["waveform/1", "waveform/2", "waveform/3", "waveform/4"]) == set(
        config.waveform_map.keys()
    )


def test_add_waveform_duplicate(config):
    """Test if error is raised when waveform that already exists is added."""
    waveform1 = Waveform(name="waveform/1")
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


def test_replace_waveform(config):
    """Test if error is raised when group that already exists at a path is added."""

    path = ["ec_launchers", "beams", "steering_angles"]
    waveform1 = Waveform(name="waveform/1")
    waveform2 = Waveform(name="waveform/1")
    waveform3 = Waveform(name="waveform/3")
    config.add_waveform(waveform1, path)
    assert config["ec_launchers"]["beams"]["steering_angles"]["waveform/1"] == waveform1
    config.replace_waveform(waveform2)
    assert config["ec_launchers"]["beams"]["steering_angles"]["waveform/1"] == waveform2
    with pytest.raises(ValueError):
        config.replace_waveform(waveform3)


def test_remove_waveform(config):
    """Test if waveforms are removed correctly from configuration."""

    waveform1 = Waveform(name="waveform/1")
    config.add_waveform(waveform1, ["ec_launchers", "beams", "steering_angles"])

    assert "waveform/1" in config.waveform_map
    assert config["waveform/1"] == waveform1
    config.remove_waveform("waveform/1")
    assert "waveform/1" not in config.waveform_map
    with pytest.raises(KeyError):
        assert config["waveform/1"] == waveform1

    with pytest.raises(ValueError):
        config.remove_waveform("waveform/1")


def test_remove_group(config):
    """Test if groups are removed correctly from configuration."""

    waveform1 = Waveform(name="waveform/1")
    waveform2 = Waveform(name="waveform/2")
    waveform3 = Waveform(name="waveform/3")

    config.add_waveform(waveform1, ["ec_launchers", "beams", "steering_angles"])
    config.add_waveform(waveform2, ["ec_launchers", "beams", "phase_angles"])
    config.add_waveform(waveform3, ["ec_launchers", "beams"])

    assert config["ec_launchers"]["beams"]["steering_angles"]["waveform/1"] == waveform1
    assert config["ec_launchers"]["beams"]["phase_angles"]["waveform/2"] == waveform2

    config.remove_group(["ec_launchers", "beams", "steering_angles"])
    with pytest.raises(KeyError):
        config["ec_launchers"]["beams"]["steering_angles"]
    with pytest.raises(KeyError):
        config["waveform/1"]

    config.remove_group(["ec_launchers", "beams"])
    with pytest.raises(KeyError):
        config["ec_launchers"]["beams"]
    with pytest.raises(KeyError):
        config["waveform/2"]
    with pytest.raises(KeyError):
        config["waveform/3"]

    assert not config["ec_launchers"].groups
    assert not config.waveform_map


def test_remove_root_group(config):
    """Test if root group is removed correctly from configuration."""

    waveform1 = Waveform(name="waveform/1")
    config.add_waveform(waveform1, ["ec_launchers", "beams", "steering_angles"])
    config.remove_group(["ec_launchers"])
    with pytest.raises(KeyError):
        config["ec_launchers"]


def test_get_item(config):
    """Test if __getitem__ returns the correct waveform."""

    path = ["ec_launchers", "beams", "steering_angles"]
    waveform1 = Waveform(name="waveform/1")
    config.add_waveform(waveform1, path)
    assert config["ec_launchers"]["beams"]["steering_angles"]["waveform/1"] == waveform1


def test_dump():
    """Check if YAML dump contains all waveforms in configuration."""

    yaml_str = """
    ec_launchers:
      beams:
        power_launched:
          ec_launchers/beam(0)/power_launched: 
          - {to: 8.33e5, duration: 20} 
          - {type: constant, duration: 20}
          - {type: smooth, duration: 25, to: 0}"""
    config = WaveformConfiguration()
    config.dd_version = "4.0.0"
    config.parser.load_yaml(yaml_str)

    new_waveform1_str = """
    ec_launchers/beam(1)/quantity:
    - {type: sine, amplitude: 3}
    - {type: smooth, to: 0}
    """
    new_waveform2_str = "ec_launchers/beam(2)/quantity: 3"

    # add new waveforms
    yaml_parser = YamlParser(config)
    waveform1 = yaml_parser.parse_waveform(new_waveform1_str)
    waveform2 = yaml_parser.parse_waveform(new_waveform2_str)
    config.add_waveform(waveform1, ["ec_launchers", "beams"])
    config.add_waveform(waveform2, ["ec_launchers", "beams"])
    dump = config.dump()

    new_config = WaveformConfiguration()
    new_config.parser.load_yaml(dump)
    old_waveform = new_config["ec_launchers/beam(0)/power_launched"]
    new_waveform1 = new_config["ec_launchers/beam(1)/quantity"]
    new_waveform2 = new_config["ec_launchers/beam(2)/quantity"]

    assert len(new_waveform1.tendencies) == 2
    assert isinstance(new_waveform1.tendencies[0], SineWaveTendency)
    assert new_waveform1.tendencies[0].user_amplitude == 3
    assert isinstance(new_waveform1.tendencies[1], SmoothTendency)
    assert new_waveform1.tendencies[1].user_to == 0

    assert len(new_waveform2.tendencies) == 1
    assert isinstance(new_waveform2.tendencies[0], ConstantTendency)
    assert new_waveform2.tendencies[0].user_value == 3

    assert len(old_waveform.tendencies) == 3
    assert isinstance(old_waveform.tendencies[0], LinearTendency)
    assert old_waveform.tendencies[0].user_to == 8.33e5
    assert old_waveform.tendencies[0].user_duration == 20
    assert isinstance(old_waveform.tendencies[1], ConstantTendency)
    assert old_waveform.tendencies[1].user_duration == 20
    assert isinstance(old_waveform.tendencies[2], SmoothTendency)
    assert old_waveform.tendencies[2].user_to == 0
    assert old_waveform.tendencies[2].user_duration == 25
    new_dump = new_config.dump()
    assert new_dump == dump


def test_dump_comments():
    """Check if comments for waveforms are preserved."""

    yaml_str = dedent("""
    ec_launchers:
      beams:
        power_launched:
          ec_launchers/beam(0)/power_launched: # comment1
          - {to: 8.33e5, duration: 20} # comment2
          - {type: constant, duration: 20}
          # comment3
          - {duration: 25, to: 0}""")
    config = WaveformConfiguration()
    config.parser.load_yaml(yaml_str)
    dumped_yaml = config.dump()
    assert yaml_str.strip() == dumped_yaml.strip()


def test_load_yaml_duplicate():
    """Check if configuration fails to load if there are duplicate entries."""
    yaml_str = """
    ec_launchers:
      ec_launchers/beam(2)/phase/angle: 1.23
      ec_launchers/beam(2)/phase/angle: 1.23
    """
    config = WaveformConfiguration()
    config.parser.load_yaml(yaml_str)
    assert config.load_error
    assert not config.groups
    assert not config.waveform_map


def test_load_yaml_globals():
    """Check if global variables are loaded from YAML."""
    yaml_str = """
    globals:
      dd_version: 3.42.0
      machine_description: 
        ec_launchers: imas:hdf5?path=testdb
    ec_launchers:
      ec_launchers/beam(1)/phase/angle: 1e-3
    """
    config = WaveformConfiguration()
    config.parser.load_yaml(yaml_str)
    assert config.dd_version == "3.42.0"
    assert config.machine_description["ec_launchers"] == "imas:hdf5?path=testdb"

    yaml_str = """
    ec_launchers:
      ec_launchers/beam(1)/phase/angle: 1e-3
    """
    config.parser.load_yaml(yaml_str)
    assert not config.dd_version
    assert not config.machine_description
