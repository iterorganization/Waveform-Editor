import numpy as np
from pytest import approx

from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = SawtoothWaveTendency(duration=1, base=0, amplitude=1, frequency=1)
    assert tendency.get_start_value() == approx(0)
    assert tendency.get_end_value() == approx(0)
    assert tendency.get_derivative_start() == approx(2)
    assert tendency.get_derivative_end() == approx(2)

    tendency = SawtoothWaveTendency(
        duration=1, base=0, amplitude=1, frequency=1, phase=np.pi / 2
    )
    assert tendency.get_start_value() == approx(0.5)
    assert tendency.get_end_value() == approx(0.5)
    assert tendency.get_derivative_start() == approx(2)
    assert tendency.get_derivative_end() == approx(2)

    tendency = SawtoothWaveTendency(
        duration=1, base=0, amplitude=1, frequency=1, phase=np.pi / 4
    )
    assert tendency.get_start_value() == approx(0.25)
    assert tendency.get_end_value() == approx(0.25)
    assert tendency.get_derivative_start() == approx(2)
    assert tendency.get_derivative_end() == approx(2)


def test_generate():
    """
    Check the generated values.
    """
    tendency = SawtoothWaveTendency(
        start=0, duration=1, amplitude=3, max=6, phase=np.pi / 2, frequency=1
    )
    time, values = tendency.generate()
    assert np.allclose(time, [0, 0.25, 0.25, 1])
    assert np.allclose(values, [4.5, 6, 0, 4.5])
