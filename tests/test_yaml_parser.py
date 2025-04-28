import pytest
from pytest import approx

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency
from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency
from waveform_editor.yaml_parser import YamlParser


@pytest.fixture
def config():
    config = WaveformConfiguration()
    config.dd_version = "4.0.0"
    return config


@pytest.fixture
def yaml_parser(config):
    return config.parser


def test_yaml_parser(yaml_parser):
    """Test loading a yaml file as a string."""
    with open("tests/tendencies/test_yaml/test.yaml") as file:
        yaml_file = file.read()
    waveform = yaml_parser.parse_waveform(yaml_file)
    assert_tendencies_correct(waveform.tendencies)
    assert not waveform.annotations
    assert not yaml_parser.parse_errors

    # Invalid configuration
    with open("tests/tendencies/test_yaml/test_invalid_config.yaml") as file:
        yaml_file = file.read()
    waveform = yaml_parser.parse_waveform(yaml_file)
    assert waveform.annotations
    assert not yaml_parser.parse_errors

    # Invalid YAML
    with open("tests/tendencies/test_yaml/test_invalid_yaml.yaml") as file:
        yaml_file = file.read()
    waveform = yaml_parser.parse_waveform(yaml_file)
    assert not waveform.tendencies
    assert yaml_parser.parse_errors


def assert_tendencies_correct(tendencies):
    """Assert that the tendencies contain the correct parameters."""
    assert isinstance(tendencies[0], LinearTendency)
    assert tendencies[0].start == approx(0)
    assert tendencies[0].end == approx(5)
    assert tendencies[0].duration == approx(5)
    assert tendencies[0].from_ == approx(0)
    assert tendencies[0].to == approx(8)

    assert isinstance(tendencies[1], SineWaveTendency)
    assert tendencies[1].start == approx(5)
    assert tendencies[1].end == approx(9)
    assert tendencies[1].duration == approx(4)
    assert tendencies[1].amplitude == approx(2)
    assert tendencies[1].frequency == approx(1)
    assert tendencies[1].base == approx(8)

    assert isinstance(tendencies[2], SawtoothWaveTendency)
    assert tendencies[2].start == approx(9)
    assert tendencies[2].end == approx(13)
    assert tendencies[2].duration == approx(4)
    assert tendencies[2].amplitude == approx(2)
    assert tendencies[2].frequency == approx(1)
    assert tendencies[2].base == approx(8)

    assert isinstance(tendencies[3], SquareWaveTendency)
    assert tendencies[3].start == approx(13)
    assert tendencies[3].end == approx(17)
    assert tendencies[3].duration == approx(4)
    assert tendencies[3].amplitude == approx(2)
    assert tendencies[3].frequency == approx(1)
    assert tendencies[3].base == approx(8)

    assert isinstance(tendencies[4], TriangleWaveTendency)
    assert tendencies[4].start == approx(17)
    assert tendencies[4].end == approx(21)
    assert tendencies[4].duration == approx(4)
    assert tendencies[4].amplitude == approx(2)
    assert tendencies[4].frequency == approx(1)
    assert tendencies[4].base == approx(8)

    assert isinstance(tendencies[5], ConstantTendency)
    assert tendencies[5].start == approx(21)
    assert tendencies[5].end == approx(24)
    assert tendencies[5].duration == approx(3)
    assert tendencies[5].value == approx(8)

    assert isinstance(tendencies[6], SmoothTendency)
    assert tendencies[6].start == approx(24)
    assert tendencies[6].end == approx(26)
    assert tendencies[6].duration == approx(2)
    assert tendencies[6].from_ == approx(8)
    assert tendencies[6].to == approx(0)


def test_scientific_notation(yaml_parser):
    """Test if scientific notation is parsed correctly."""
    waveforms = {
        "waveform:\n- {type: linear, to: 1.5e5}": 1.5e5,
        "waveform:\n- {type: linear, to: 1.5e+5}": 1.5e5,
        "waveform:\n- {type: linear, to: 1.5E+5}": 1.5e5,
        "waveform:\n- {type: linear, to: 1.5e-5}": 1.5e-5,
        "waveform:\n- {type: linear, to: 1.5E-5}": 1.5e-5,
        "waveform:\n- {type: linear, to: 1e5}": 1e5,
        "waveform:\n- {type: linear, to: 1e+5}": 1e5,
        "waveform:\n- {type: linear, to: 1E+5}": 1e5,
        "waveform:\n- {type: linear, to: 1e-5}": 1e-5,
        "waveform:\n- {type: linear, to: 1E-5}": 1e-5,
        "waveform:\n- {type: linear, to: 0e5}": 0.0,
        "waveform:\n- {type: linear, to: 0E0}": 0.0,
        "waveform:\n- {type: linear, to: -1.5e5}": -1.5e5,
        "waveform:\n- {type: linear, to: -1E+5}": -1e5,
        "waveform:\n- {type: linear, to: -1.5e-5}": -1.5e-5,
    }

    for waveform, expected_value in waveforms.items():
        waveform = yaml_parser.parse_waveform(waveform)
        assert waveform.tendencies[0].to == expected_value


def test_constant_shorthand_notation(yaml_parser):
    """Test if shorthand notation is parsed correctly."""

    waveforms = {"waveform: 5": 5, "waveform: 1.23": 1.23}

    for waveform, expected_value in waveforms.items():
        waveform = yaml_parser.parse_waveform(waveform)
        assert len(waveform.tendencies) == 1
        assert isinstance(waveform.tendencies[0], ConstantTendency)
        assert waveform.tendencies[0].value == expected_value
        assert not waveform.annotations
        assert not yaml_parser.parse_errors


def test_load_yaml(config):
    """Test if yaml is loaded correctly."""
    yaml_str = """
    ec_launchers:
      beams:
        power_launched:
          ec_launchers/beam(:)/power_launched:
              - {to: 8.33e5, duration: 20} # implicit linear ramp
              - {type: constant, duration: 20}
              - {duration: 25, to: 0} # implicit linear back to 0
        phase_angles:
          ec_launchers/beam(1)/phase/angle: 1
          ec_launchers/beam(2)/phase/angle: 2e3
          ec_launchers/beam(3)/phase/angle: 3.5
    globals:
      dd_version: 3.42.0
    """
    parser = YamlParser(config)
    parser.load_yaml(yaml_str)
    root_group = config.groups["ec_launchers"]
    power_launched_waveform = root_group["beams"]["power_launched"][
        "ec_launchers/beam(:)/power_launched"
    ]

    assert power_launched_waveform.tendencies[0].to == 8.33e5
    assert power_launched_waveform.tendencies[0].duration == 20
    assert power_launched_waveform.tendencies[1].duration == 20
    assert power_launched_waveform.tendencies[2].duration == 25
    assert power_launched_waveform.tendencies[2].to == 0

    phase_angles = root_group["beams"]["phase_angles"]
    assert phase_angles["ec_launchers/beam(1)/phase/angle"].tendencies[0].value == 1
    assert phase_angles["ec_launchers/beam(2)/phase/angle"].tendencies[0].value == 2e3
    assert phase_angles["ec_launchers/beam(3)/phase/angle"].tendencies[0].value == 3.5

    with pytest.raises(KeyError):
        root_group["asdf"]
    with pytest.raises(KeyError):
        root_group["beams"]["asdf/asdf"]


def test_load_yaml_globals():
    """Test if globals contain the correct dd version."""
    yaml_str = """
    globals:
      dd_version: 3.42.0
      machine_description: 
        ec_launchers: imas:hdf5?path=test_md
        equilibrium: imas:hdf5?path=test_md2
    """
    config = WaveformConfiguration()
    parser = YamlParser(config)
    parser.load_yaml(yaml_str)
    assert not config.groups
    assert not config.waveform_map
    assert config.dd_version == "3.42.0"
    assert config.machine_description["ec_launchers"] == "imas:hdf5?path=test_md"
    assert config.machine_description["equilibrium"] == "imas:hdf5?path=test_md2"
    assert not config.load_error

    yaml_str = """
    globals:
      machine_description: 
        ec_launchers: imas:hdf5?path=test_md
        equilibrium: imas:hdf5?path=test_md2
    """
    parser.load_yaml(yaml_str)
    assert not config.groups
    assert not config.waveform_map
    assert config.dd_version is None
    assert config.machine_description["ec_launchers"] == "imas:hdf5?path=test_md"
    assert config.machine_description["equilibrium"] == "imas:hdf5?path=test_md2"
    assert not config.load_error

    yaml_str = """
    globals:
      machine_description: imas:hdf5?path=test_md
    """
    parser.load_yaml(yaml_str)
    assert config.load_error
    assert not config.groups
    assert not config.waveform_map
    assert config.dd_version is None
    assert not config.machine_description

    yaml_str = """
    globals:
      dd_version: 4.0.0
    """
    parser.load_yaml(yaml_str)
    assert not config.groups
    assert not config.waveform_map
    assert config.dd_version == "4.0.0"
    assert not config.machine_description
    assert not config.load_error
