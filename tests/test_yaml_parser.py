from pytest import approx

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency
from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency
from waveform_editor.yaml_parser import YamlParser


def test_yaml_parser():
    """Test loading a yaml file as a string."""
    # Valid YAML
    with open("tests/tendencies/test_yaml/test.yaml") as file:
        yaml_file = file.read()
    yaml_parser = YamlParser()
    yaml_parser.parse_waveforms(yaml_file)
    assert_tendencies_correct(yaml_parser.waveform.tendencies)
    assert not yaml_parser.waveform.annotations
    assert not yaml_parser.has_yaml_error

    # Invalid configuration
    with open("tests/tendencies/test_yaml/test_invalid_config.yaml") as file:
        yaml_file = file.read()
    yaml_parser = YamlParser()
    yaml_parser.parse_waveforms(yaml_file)
    assert yaml_parser.waveform.annotations
    assert not yaml_parser.has_yaml_error

    # Invalid YAML
    with open("tests/tendencies/test_yaml/test_invalid_yaml.yaml") as file:
        yaml_file = file.read()
    yaml_parser = YamlParser()
    yaml_parser.parse_waveforms(yaml_file)
    assert yaml_parser.waveform.annotations
    assert yaml_parser.has_yaml_error


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


def test_scientific_notation():
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

    yaml_parser = YamlParser()

    for waveform, expected_value in waveforms.items():
        yaml_parser.parse_waveforms(waveform)
        assert yaml_parser.waveform.tendencies[0].to == expected_value


def test_constant_shorthand_notation():
    """Test if shorthand notation is parsed correctly."""

    waveforms = {"waveform: 5": 5, "waveform: 1.23": 1.23}
    yaml_parser = YamlParser()

    for waveform, expected_value in waveforms.items():
        yaml_parser.parse_waveforms(waveform)
        assert len(yaml_parser.waveform.tendencies) == 1
        assert isinstance(yaml_parser.waveform.tendencies[0], ConstantTendency)
        assert yaml_parser.waveform.tendencies[0].value == expected_value
        assert not yaml_parser.waveform.annotations
        assert not yaml_parser.has_yaml_error
