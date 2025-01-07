from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.sine_wave import SineWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency
from waveform_editor.yaml_parser import YamlParser


def test_yaml_parser():
    yaml_parser = YamlParser()
    yaml_parser.parse_waveforms_from_file("tests/test_yaml/test.yaml")
    tendencies = yaml_parser.tendencies

    assert isinstance(tendencies[0], LinearTendency)
    assert tendencies[0].start == 0
    assert tendencies[0].end == 5
    assert tendencies[0].duration == 5
    assert tendencies[0].from_value == 0
    assert tendencies[0].to_value == 8

    assert isinstance(tendencies[1], SineWaveTendency)
    assert tendencies[1].start == 5
    assert tendencies[1].end == 9
    assert tendencies[1].duration == 4
    assert tendencies[1].amplitude == 2
    assert tendencies[1].frequency == 1
    assert tendencies[1].base == 8

    assert isinstance(tendencies[2], ConstantTendency)
    assert tendencies[2].start == 9
    assert tendencies[2].end == 12
    assert tendencies[2].duration == 3
    assert tendencies[2].value == 8

    assert isinstance(tendencies[3], SmoothTendency)
    assert tendencies[3].start == 12
    assert tendencies[3].end == 14
    assert tendencies[3].duration == 2
    assert tendencies[3].from_value == 8
    assert tendencies[3].to_value == 0
