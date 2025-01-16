import numpy as np

from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = SquareWaveTendency(duration=1)
    assert tendency.get_start_value() == 1
    assert tendency.get_end_value() == 1
    assert tendency.get_derivative_start() == 0
    assert tendency.get_derivative_end() == 0

    tendency = SquareWaveTendency(duration=1.75)
    assert tendency.get_start_value() == 1
    assert tendency.get_end_value() == -1
    assert tendency.get_derivative_start() == 0
    assert tendency.get_derivative_end() == 0

    tendency = SquareWaveTendency(duration=1, phase=np.pi / 2)
    assert tendency.get_start_value() == 1
    assert tendency.get_end_value() == 1
    assert tendency.get_derivative_start() == 0
    assert tendency.get_derivative_end() == 0

    tendency = SquareWaveTendency(duration=1, phase=1.5 * np.pi)
    assert tendency.get_start_value() == -1
    assert tendency.get_end_value() == -1
    assert tendency.get_derivative_start() == 0
    assert tendency.get_derivative_end() == 0
