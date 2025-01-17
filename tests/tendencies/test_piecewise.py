import numpy as np
import pytest
from pytest import approx

from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency


def test_empty():
    """Test empty tendency."""
    with pytest.raises(ValueError):
        PiecewiseLinearTendency()

    with pytest.raises(ValueError):
        PiecewiseLinearTendency(time=np.array([1, 2, 3]))

    with pytest.raises(ValueError):
        PiecewiseLinearTendency(value=np.array([1, 2, 3]))


def test_filled():
    """Test value of filled tendency."""
    tendency = PiecewiseLinearTendency(time=[1, 2, 3], value=[2, 4, 6])
    assert np.all(tendency.time == np.array([1, 2, 3]))
    assert np.all(tendency.value == np.array([2, 4, 6]))

    tendency = PiecewiseLinearTendency(
        time=np.array([1, 2, 3]), value=np.array([2, 4, 6])
    )
    assert np.all(tendency.time == np.array([1, 2, 3]))
    assert np.all(tendency.value == np.array([2, 4, 6]))

    tendency = PiecewiseLinearTendency(
        time=np.array([1.1, 2.2, 3.3]), value=np.array([9.9, 5.5, 2.2])
    )
    assert np.all(tendency.time == np.array([1.1, 2.2, 3.3]))
    assert np.all(tendency.value == np.array([9.9, 5.5, 2.2]))


def test_filled_valid():
    """Test value of filled tendency with invalid parameters."""
    with pytest.raises(ValueError):
        PiecewiseLinearTendency(time=np.array([3, 2, 1]), value=np.array([1, 2, 3]))

    with pytest.raises(ValueError):
        PiecewiseLinearTendency(time=np.array([1, 2]), value=np.array([1, 2, 3]))

    with pytest.raises(ValueError):
        PiecewiseLinearTendency(time=np.array([1]), value=np.array([1]))


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = PiecewiseLinearTendency(
        time=np.array([1, 2, 3]), value=np.array([2, 4, 0])
    )
    assert tendency.get_start_value() == 2
    assert tendency.get_end_value() == 0
    assert tendency.get_derivative_start() == approx(2)
    assert tendency.get_derivative_end() == approx(-4)


def test_generate():
    """
    Check the generated values.
    """
    tendency = PiecewiseLinearTendency(
        time=np.array([1, 2, 3]), value=np.array([2, 4, 6])
    )
    time, values = tendency.generate()
    assert np.all(time == [1, 2, 3])
    assert np.all(values == [2, 4, 6])


def test_generate_interpolate():
    """
    Check the generated interpolated values.
    """
    tendency = PiecewiseLinearTendency(
        time=np.array([1, 2, 3]), value=np.array([2, 4, 8])
    )
    time, values = tendency.generate(time=[1.0, 1.5, 2.0, 2.5, 3.0])
    assert np.all(time == [1.0, 1.5, 2.0, 2.5, 3.0])
    assert np.allclose(values, [2.0, 3.0, 4.0, 6.0, 8.0])

    with pytest.raises(ValueError):
        time, values = tendency.generate(time=[0.5, 1.5, 2.0, 2.5, 3.0])

    with pytest.raises(ValueError):
        time, values = tendency.generate(time=[1.0, 1.5, 2.0, 2.5, 3.5])
