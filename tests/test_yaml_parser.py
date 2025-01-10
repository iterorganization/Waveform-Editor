from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency
from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency
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
    assert tendencies[0].from_ == 0
    assert tendencies[0].to == 8

    assert isinstance(tendencies[1], SineWaveTendency)
    assert tendencies[1].start == 5
    assert tendencies[1].end == 9
    assert tendencies[1].duration == 4
    assert tendencies[1].amplitude == 2
    assert tendencies[1].frequency == 1
    assert tendencies[1].base == 8

    assert isinstance(tendencies[2], SawtoothWaveTendency)
    assert tendencies[2].start == 9
    assert tendencies[2].end == 13
    assert tendencies[2].duration == 4
    assert tendencies[2].amplitude == 2
    assert tendencies[2].frequency == 1
    assert tendencies[2].base == 8

    assert isinstance(tendencies[3], SquareWaveTendency)
    assert tendencies[3].start == 13
    assert tendencies[3].end == 17
    assert tendencies[3].duration == 4
    assert tendencies[3].amplitude == 2
    assert tendencies[3].frequency == 1
    assert tendencies[3].base == 8

    assert isinstance(tendencies[4], TriangleWaveTendency)
    assert tendencies[4].start == 17
    assert tendencies[4].end == 21
    assert tendencies[4].duration == 4
    assert tendencies[4].amplitude == 2
    assert tendencies[4].frequency == 1
    assert tendencies[4].base == 8

    assert isinstance(tendencies[5], ConstantTendency)
    assert tendencies[5].start == 21
    assert tendencies[5].end == 24
    assert tendencies[5].duration == 3
    assert tendencies[5].value == 8

    assert isinstance(tendencies[6], SmoothTendency)
    assert tendencies[6].start == 24
    assert tendencies[6].end == 26
    assert tendencies[6].duration == 2
    assert tendencies[6].from_ == 8
    assert tendencies[6].to == 0
