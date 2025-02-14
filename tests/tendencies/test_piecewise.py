import numpy as np
from pytest import approx

from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency


def test_empty():
    """Test empty tendency."""
    tendency = PiecewiseLinearTendency()
    assert tendency.annotations

    tendency = PiecewiseLinearTendency(user_time=np.array([1, 2, 3]))
    assert tendency.annotations

    PiecewiseLinearTendency(user_value=np.array([1, 2, 3]))
    assert tendency.annotations


def test_filled():
    """Test value of filled tendency."""
    tendency = PiecewiseLinearTendency(user_time=[1, 2, 3], user_value=[2, 4, 6])
    assert np.all(tendency.time == np.array([1, 2, 3]))
    assert np.all(tendency.value == np.array([2, 4, 6]))
    assert not tendency.annotations

    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]), user_value=np.array([2, 4, 6])
    )
    assert np.all(tendency.time == np.array([1, 2, 3]))
    assert np.all(tendency.value == np.array([2, 4, 6]))
    assert not tendency.annotations

    tendency = PiecewiseLinearTendency(
        user_time=np.array([1.1, 2.2, 3.3]), user_value=np.array([9.9, 5.5, 2.2])
    )
    assert np.all(tendency.time == np.array([1.1, 2.2, 3.3]))
    assert np.all(tendency.value == np.array([9.9, 5.5, 2.2]))
    assert not tendency.annotations


def test_filled_invalid():
    """Test value of filled tendency with invalid parameters."""
    tendency = PiecewiseLinearTendency(
        user_time=np.array([3, 2, 1]), user_value=np.array([1, 2, 3])
    )
    assert tendency.annotations

    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2]), user_value=np.array([1, 2, 3])
    )
    assert tendency.annotations

    tendency = PiecewiseLinearTendency(
        user_time=np.array([1]), user_value=np.array([1])
    )
    assert tendency.annotations

    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 1, 2]), user_value=np.array([1, 2, 3])
    )
    assert tendency.annotations

    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 0, 2]), user_value=np.array([1, 2, 3])
    )
    assert tendency.annotations

    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]), user_value=np.array([1, 2, 3]), user_start=1
    )
    assert tendency.annotations

    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]),
        user_value=np.array([1, 2, 3]),
        user_start=1,
        user_duration=2,
        user_end=3,
    )
    assert tendency.annotations


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]), user_value=np.array([2, 4, 0])
    )
    assert tendency.start_value == 2
    assert tendency.end_value == 0
    assert tendency.start_derivative == approx(2)
    assert tendency.end_derivative == approx(-4)
    assert not tendency.annotations


def test_generate():
    """
    Check the generated values.
    """
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]), user_value=np.array([2, 4, 6])
    )
    time, values = tendency.get_value()
    assert np.all(time == [1, 2, 3])
    assert np.all(values == [2, 4, 6])
    assert not tendency.annotations


def test_get_value_bounds():
    """
    Check the generated values outside of the time array.
    """
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]), user_value=np.array([2, 4, 8])
    )
    _, values = tendency.get_value(np.array([0.0, 0.5, 1.0, 3.0, 3.5, 4.0]))
    assert np.allclose(values, [2, 2, 2, 8, 8, 8])
    assert not tendency.annotations


def test_get_value_interpolate():
    """
    Check the generated interpolated values.
    """
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]), user_value=np.array([2, 4, 8])
    )
    time, values = tendency.get_value(np.array([1.0, 1.5, 2.0, 2.5, 3.0]))
    assert np.all(time == [1.0, 1.5, 2.0, 2.5, 3.0])
    assert np.allclose(values, [2.0, 3.0, 4.0, 6.0, 8.0])
    assert not tendency.annotations

    # Request value before time range
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]), user_value=np.array([2, 4, 8])
    )
    time, values = tendency.get_value(np.array([0.5, 1.5, 2.0, 2.5, 3.0]))
    assert np.allclose(values, [2.0, 3.0, 4.0, 6.0, 8.0])
    assert not tendency.annotations

    # Request after time range
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3]), user_value=np.array([2, 4, 8])
    )
    time, values = tendency.get_value(np.array([1.0, 1.5, 2.0, 2.5, 3.5]))
    assert np.allclose(values, [2.0, 3.0, 4.0, 6.0, 8.0])
    assert not tendency.annotations


def test_get_derivative_interpolate():
    """
    Check the generated interpolated derivative values.
    """
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3, 5, 7]), user_value=np.array([2, 4, 3, 2, 6])
    )
    derivatives = tendency.get_derivative(
        time=np.array([1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7])
    )
    expected_derivatives = [2, 2, -1, -1, -0.5, -0.5, -0.5, -0.5, 2, 2, 2, 2, 2]
    assert np.allclose(derivatives, expected_derivatives)
    assert not tendency.annotations

    # Request derivative before time range
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3, 5, 7]), user_value=np.array([2, 4, 3, 2, 6])
    )
    derivatives = tendency.get_derivative(
        time=np.array([0.5, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7])
    )
    expected_derivatives = [2, 2, -1, -1, -0.5, -0.5, -0.5, -0.5, 2, 2, 2, 2, 2]
    assert np.allclose(derivatives, expected_derivatives)
    assert not tendency.annotations

    # Request derivative after time range
    tendency = PiecewiseLinearTendency(
        user_time=np.array([1, 2, 3, 5, 7]), user_value=np.array([2, 4, 3, 2, 6])
    )
    derivatives = tendency.get_derivative(
        time=np.array([1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7.5])
    )
    expected_derivatives = [2, 2, -1, -1, -0.5, -0.5, -0.5, -0.5, 2, 2, 2, 2, 2]
    assert np.allclose(derivatives, expected_derivatives)
    assert not tendency.annotations
