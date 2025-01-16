import numpy as np
from pytest import approx

from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = SineWaveTendency(duration=1)
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(2 * np.pi)
    assert tendency.get_derivative_end() == approx(2 * np.pi)

    tendency = SineWaveTendency(duration=1, phase=np.pi / 2)
    assert tendency.get_start_value() == approx(1)
    assert tendency.get_end_value() == approx(1)
    assert tendency.get_derivative_start() == approx(0)
    assert tendency.get_derivative_end() == approx(0)

    tendency = SineWaveTendency(duration=1, phase=np.pi)
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(-2 * np.pi)
    assert tendency.get_derivative_end() == approx(-2 * np.pi)
