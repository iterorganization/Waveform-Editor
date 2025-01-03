from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.sine_wave import SineWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency
from waveform_editor.yaml_parser import YamlParser


def test_yaml_parser():
    yaml_parser = YamlParser()
    yaml_parser.parse_waveforms("tests/test_yaml/test.yaml")
    assert isinstance(yaml_parser.tendencies[0], LinearTendency)
    assert isinstance(yaml_parser.tendencies[1], SineWaveTendency)
    assert isinstance(yaml_parser.tendencies[2], ConstantTendency)
    assert isinstance(yaml_parser.tendencies[3], SmoothTendency)
