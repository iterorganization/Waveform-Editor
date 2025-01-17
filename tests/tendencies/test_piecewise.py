import pytest
from pytest import approx

from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency


def test_empty():
    """Test empty tendency."""
    with pytest.raises(ValueError):
        PiecewiseLinearTendency()

    with pytest.raises(ValueError):
        PiecewiseLinearTendency(time=[1, 2, 3])

    with pytest.raises(ValueError):
        PiecewiseLinearTendency(value=[1, 2, 3])


def test_filled():
    """Test value of filled tendency."""
    tendency = PiecewiseLinearTendency(time=[1, 2, 3], value=[2, 4, 6])
    assert tendency.time == [1, 2, 3]
    assert tendency.value == [2, 4, 6]

    tendency = PiecewiseLinearTendency(time=[1.1, 2.2, 3.3], value=[9.9, 5.5, 2.2])
    assert tendency.time == [1.1, 2.2, 3.3]
    assert tendency.value == [9.9, 5.5, 2.2]


def test_filled_valid():
    """Test value of filled tendency with invalid parameters."""
    with pytest.raises(ValueError):
        PiecewiseLinearTendency(time=[3, 2, 1], value=[1, 2, 3])

    with pytest.raises(ValueError):
        PiecewiseLinearTendency(time=[1, 2], value=[1, 2, 3])

    with pytest.raises(ValueError):
        PiecewiseLinearTendency(time=[1], value=[1])


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = PiecewiseLinearTendency(time=[1, 2, 3], value=[2, 4, 0])
    assert tendency.get_start_value() == 2
    assert tendency.get_end_value() == 0
    assert tendency.get_derivative_start() == approx(2)
    assert tendency.get_derivative_end() == approx(-4)


def test_generate():
    """
    Check the generated values.
    """
    tendency = PiecewiseLinearTendency(time=[1, 2, 3], value=[2, 4, 6])
    time, values = tendency.generate()
    assert time == [1, 2, 3]
    assert values == [2, 4, 6]
