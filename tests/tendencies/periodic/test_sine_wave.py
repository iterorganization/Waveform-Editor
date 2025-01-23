import numpy as np
from pytest import approx

from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = SineWaveTendency(
        user_duration=1, user_base=0, user_amplitude=1, user_frequency=1
    )
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(2 * np.pi)
    assert tendency.get_derivative_end() == approx(2 * np.pi)

    tendency = SineWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi / 2,
    )
    assert tendency.get_start_value() == approx(1)
    assert tendency.get_end_value() == approx(1)
    assert tendency.get_derivative_start() == approx(0)
    assert tendency.get_derivative_end() == approx(0)

    tendency = SineWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi,
    )
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(-2 * np.pi)
    assert tendency.get_derivative_end() == approx(-2 * np.pi)


def test_generate():
    """
    Check the generated values.
    """
    tendency = SineWaveTendency(
        user_start=0, user_duration=1, user_base=2, user_amplitude=3, user_phase=1
    )
    time, values = tendency.generate()
    assert np.all(time == np.linspace(0, 1, 101))
    assert np.allclose(values, 2 + 3 * np.sin(2 * np.pi * time + 1))
