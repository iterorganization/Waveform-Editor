import numpy as np
from pytest import approx

from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = TriangleWaveTendency(duration=1, base=0, amplitude=1, frequency=1)
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(4)
    assert tendency.get_derivative_end() == approx(4)

    tendency = TriangleWaveTendency(
        duration=1, base=0, amplitude=1, frequency=1, phase=np.pi / 4
    )
    assert tendency.get_start_value() == approx(0.5)
    assert tendency.get_end_value() == approx(0.5)
    assert tendency.get_derivative_start() == approx(4)
    assert tendency.get_derivative_end() == approx(4)

    tendency = TriangleWaveTendency(
        duration=1, base=0, amplitude=1, frequency=1, phase=np.pi
    )
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(-4)
    assert tendency.get_derivative_end() == approx(-4)

    tendency = TriangleWaveTendency(
        duration=1.5, base=0, amplitude=1, frequency=1, phase=np.pi
    )
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(-4)
    assert tendency.get_derivative_end() == approx(4)


def test_generate():
    """
    Check the generated values.
    """
    tendency = TriangleWaveTendency(
        start=0, duration=1.5, base=6, min=3, phase=0, frequency=1
    )
    time, values = tendency.generate()
    assert np.allclose(time, [0, 0.25, 0.75, 1.25, 1.5])
    assert np.allclose(values, [6, 9, 3, 9, 6])
