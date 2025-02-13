import numpy as np
from pytest import approx

from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = SawtoothWaveTendency(
        user_duration=1, user_base=0, user_amplitude=1, user_frequency=1
    )
    assert tendency.start_value == approx(0)
    assert tendency.end_value == approx(0)
    assert tendency.start_derivative == approx(2)
    assert tendency.end_derivative == approx(2)
    assert not tendency.annotations

    tendency = SawtoothWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi / 2,
    )
    assert tendency.start_value == approx(0.5)
    assert tendency.end_value == approx(0.5)
    assert tendency.start_derivative == approx(2)
    assert tendency.end_derivative == approx(2)
    assert not tendency.annotations

    tendency = SawtoothWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi / 4,
    )
    assert tendency.start_value == approx(0.25)
    assert tendency.end_value == approx(0.25)
    assert tendency.start_derivative == approx(2)
    assert tendency.end_derivative == approx(2)
    assert not tendency.annotations


def test_generate():
    """
    Check the generated values.
    """
    tendency = SawtoothWaveTendency(
        user_start=0,
        user_duration=1,
        user_amplitude=3,
        user_max=6,
        user_phase=np.pi / 2,
        user_frequency=1,
    )
    time, values = tendency.get_value()
    assert np.allclose(time, [0, 0.25, 0.25, 1])
    assert np.allclose(values, [4.5, 6, 0, 4.5])
    assert not tendency.annotations
