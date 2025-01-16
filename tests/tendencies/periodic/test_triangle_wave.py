import numpy as np
from pytest import approx

from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = TriangleWaveTendency(duration=1)
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(4)
    assert tendency.get_derivative_end() == approx(4)

    tendency = TriangleWaveTendency(duration=1, phase=np.pi / 4)
    assert tendency.get_start_value() == approx(0.5)
    assert tendency.get_end_value() == approx(0.5)
    assert tendency.get_derivative_start() == approx(4)
    assert tendency.get_derivative_end() == approx(4)

    tendency = TriangleWaveTendency(duration=1, phase=np.pi)
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(-4)
    assert tendency.get_derivative_end() == approx(-4)

    tendency = TriangleWaveTendency(duration=1.5, phase=np.pi)
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(-4)
    assert tendency.get_derivative_end() == approx(4)
