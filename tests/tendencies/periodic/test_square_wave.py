import numpy as np

from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = SquareWaveTendency(
        user_duration=1, user_base=0, user_amplitude=1, user_frequency=1
    )
    assert tendency.start_value == 1
    assert tendency.end_value == 1
    assert tendency.start_derivative == 0
    assert tendency.end_derivative == 0
    assert not tendency.annotations

    tendency = SquareWaveTendency(
        user_duration=1.75, user_base=0, user_amplitude=1, user_frequency=1
    )
    assert tendency.start_value == 1
    assert tendency.end_value == -1
    assert tendency.start_derivative == 0
    assert tendency.end_derivative == 0
    assert not tendency.annotations

    tendency = SquareWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=np.pi / 2,
    )
    assert tendency.start_value == 1
    assert tendency.end_value == 1
    assert tendency.start_derivative == 0
    assert tendency.end_derivative == 0
    assert not tendency.annotations

    tendency = SquareWaveTendency(
        user_duration=1,
        user_base=0,
        user_amplitude=1,
        user_frequency=1,
        user_phase=1.5 * np.pi,
    )
    assert tendency.start_value == -1
    assert tendency.end_value == -1
    assert tendency.start_derivative == 0
    assert tendency.end_derivative == 0
    assert not tendency.annotations


def test_generate():
    """
    Check the generated values.
    """
    tendency = SquareWaveTendency(
        user_start=0,
        user_duration=1.5,
        user_base=2,
        user_amplitude=3,
        user_phase=np.pi / 2,
        user_frequency=1,
    )
    time, values = tendency.get_value()
    assert np.allclose(time, [0, 0.25, 0.25, 0.75, 0.75, 1.25, 1.25, 1.5])
    assert np.allclose(values, [5, 5, -1, -1, 5, 5, -1, -1])
    assert not tendency.annotations
