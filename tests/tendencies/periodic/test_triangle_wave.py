import numpy as np
from pytest import approx

from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = TriangleWaveTendency(
        user_duration=1, user_base=0, user_amplitude=1, user_frequency=1
    )
    assert tendency.start_value == approx(0)
    assert tendency.end_value == approx(0)
    assert tendency.start_derivative == approx(4)
    assert tendency.end_derivative == approx(4)
    assert not tendency.annotations

    tendency = TriangleWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi / 4,
    )
    assert tendency.start_value == approx(0.5)
    assert tendency.end_value == approx(0.5)
    assert tendency.start_derivative == approx(4)
    assert tendency.end_derivative == approx(4)
    assert not tendency.annotations

    tendency = TriangleWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi,
    )
    assert tendency.start_value == approx(0)
    assert tendency.end_value == approx(0)
    assert tendency.start_derivative == approx(-4)
    assert tendency.end_derivative == approx(-4)
    assert not tendency.annotations

    tendency = TriangleWaveTendency(
        user_duration=1.5,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi,
    )
    assert tendency.start_value == approx(0)
    assert tendency.end_value == approx(0)
    assert tendency.start_derivative == approx(-4)
    assert tendency.end_derivative == approx(4)
    assert not tendency.annotations


def test_generate():
    """
    Check the generated values.
    """
    tendency = TriangleWaveTendency(
        user_start=0,
        user_duration=1.5,
        user_base=6,
        user_min=3,
        user_phase=0,
        user_frequency=1,
    )
    time, values = tendency.get_value()
    assert np.allclose(time, [0, 0.25, 0.75, 1.25, 1.5])
    assert np.allclose(values, [6, 9, 3, 9, 6])
    assert not tendency.annotations
