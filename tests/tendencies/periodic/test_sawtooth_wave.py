import numpy as np
from pytest import approx

from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = SawtoothWaveTendency(duration=1, base=0, amplitude=1, frequency=1)
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(2)
    assert tendency.get_derivative_end() == approx(2)

    tendency = SawtoothWaveTendency(
        duration=1, base=0, amplitude=1, frequency=1, phase=np.pi / 2
    )
    assert tendency.get_start_value() == approx(0.5)
    assert tendency.get_end_value() == approx(0.5)
    assert tendency.get_derivative_start() == approx(2)
    assert tendency.get_derivative_end() == approx(2)

    tendency = SawtoothWaveTendency(
        duration=1, base=0, amplitude=1, frequency=1, phase=np.pi / 4
    )
    assert tendency.get_start_value() == approx(0.25)
    assert tendency.get_end_value() == approx(0.25)
    assert tendency.get_derivative_start() == approx(2)
    assert tendency.get_derivative_end() == approx(2)
