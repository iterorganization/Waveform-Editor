import numpy as np

from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = SquareWaveTendency(duration=1, base=0, amplitude=1, frequency=1)
    assert tendency.get_start_value() == 1
    assert tendency.get_end_value() == 1
    assert tendency.get_derivative_start() == 0
    assert tendency.get_derivative_end() == 0

    tendency = SquareWaveTendency(duration=1.75, base=0, amplitude=1, frequency=1)
    assert tendency.get_start_value() == 1
    assert tendency.get_end_value() == -1
    assert tendency.get_derivative_start() == 0
    assert tendency.get_derivative_end() == 0

    tendency = SquareWaveTendency(
        duration=1, base=0, amplitude=1, frequency=1, phase=np.pi / 2
    )
    assert tendency.get_start_value() == 1
    assert tendency.get_end_value() == 1
    assert tendency.get_derivative_start() == 0
    assert tendency.get_derivative_end() == 0

    tendency = SquareWaveTendency(
        duration=1, base=0, amplitude=1, frequency=1, phase=1.5 * np.pi
    )
    assert tendency.get_start_value() == -1
    assert tendency.get_end_value() == -1
    assert tendency.get_derivative_start() == 0
    assert tendency.get_derivative_end() == 0


def test_generate():
    """
    Check the generated values.
    """
    tendency = SquareWaveTendency(
        start=0, duration=1.5, base=2, amplitude=3, phase=np.pi / 2, frequency=1
    )
    time, values = tendency.generate()
    assert np.allclose(time, [0, 0.25, 0.25, 0.75, 0.75, 1.25, 1.25, 1.5])
    assert np.allclose(values, [5, 5, -1, -1, 5, 5, -1, -1])
