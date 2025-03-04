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
    assert tendency.start_value == approx(0)
    assert tendency.end_value == approx(0)
    assert tendency.start_derivative == approx(2 * np.pi)
    assert tendency.end_derivative == approx(2 * np.pi)
    assert not tendency.annotations

    tendency = SineWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi / 2,
    )
    assert tendency.start_value == approx(1)
    assert tendency.end_value == approx(1)
    assert tendency.start_derivative == approx(0)
    assert tendency.end_derivative == approx(0)
    assert not tendency.annotations

    tendency = SineWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi,
    )
    assert tendency.start_value == approx(0)
    assert tendency.end_value == approx(0)
    assert tendency.start_derivative == approx(-2 * np.pi)
    assert tendency.end_derivative == approx(-2 * np.pi)
    assert not tendency.annotations


def test_generate():
    """
    Check the generated values.
    """
    tendency = SineWaveTendency(
        user_start=0, user_duration=1, user_base=2, user_amplitude=3, user_phase=1
    )
    time, values = tendency.get_value()
    assert np.all(time == np.linspace(0, 1, 32 + 1))
    assert np.allclose(values, 2 + 3 * np.sin(2 * np.pi * time + 1))
    assert not tendency.annotations


def test_declarative_assignment():
    tendency = SineWaveTendency(user_duration=1, user_amplitude=10, user_frequency=1)
    assert tendency.start_value == approx(0)
    assert not tendency.annotations

    tendency.user_base = 12
    assert tendency.start_value == approx(12)

    tendency.user_phase = -np.pi / 2
    assert tendency.start_value == approx(2)
