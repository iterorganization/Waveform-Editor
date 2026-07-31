import numpy as np
import pytest

from waveform_editor.tendencies.steps import StepsTendency


def test_empty():
    """Test empty tendency."""
    tendency = StepsTendency()
    assert tendency.annotations

    tendency = StepsTendency(user_time=[0, 2, 4])
    assert tendency.annotations

    tendency = StepsTendency(user_value=[1, 2, 3])
    assert tendency.annotations


def test_filled():
    """Test value of a filled tendency."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_end=6)
    assert np.all(tendency.time == np.array([0, 2, 4]))
    assert list(tendency.value) == [1, 3, 5]
    assert tendency.value_type is int
    assert tendency.start == 0
    assert tendency.end == 6
    assert not tendency.annotations


def test_string_values():
    """Test a tendency with string values."""
    tendency = StepsTendency(
        user_time=[0, 10, 20], user_value=["ohmic", "nbi", "ec"], user_end=30
    )
    assert list(tendency.value) == ["ohmic", "nbi", "ec"]
    assert tendency.value_type is str
    assert not tendency.annotations

    _, values = tendency.get_value(np.array([0, 5, 10, 15, 20, 25, 30]))
    assert list(values) == ["ohmic", "ohmic", "nbi", "nbi", "ec", "ec", "ec"]


def test_int_float_mixing():
    """Test that mixing int and float values in a single steps tendency"""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 2.5, 3], user_end=6)
    assert tendency.value_type is float
    assert not tendency.annotations


def test_mixed_value_types_not_supported():
    """Test that mixing string and numerical values is not allowed."""
    tendency = StepsTendency(user_time=[0, 10], user_value=[1, "ec"], user_end=20)
    assert tendency.annotations


def test_unsupported_value_type():
    """Test that a value which is not an int, float, or str is not supported."""
    tendency = StepsTendency(user_time=[0, 10], user_value=[1, [2, 3]], user_end=20)
    assert tendency.annotations


def test_duration_instead_of_end():
    """Test that `duration` can be used instead of `end`."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_duration=6)
    assert tendency.end == 6
    assert not tendency.annotations


def test_duration_and_end_consistent():
    """Test that providing both `duration` and `end` is fine if consistent."""
    tendency = StepsTendency(
        user_time=[0, 2, 4], user_value=[1, 3, 5], user_duration=6, user_end=6
    )
    assert tendency.end == 6
    assert not tendency.annotations


def test_duration_and_end_inconsistent():
    """Test that providing inconsistent `duration` and `end` results in an error."""
    tendency = StepsTendency(
        user_time=[0, 2, 4], user_value=[1, 3, 5], user_duration=6, user_end=10
    )
    assert tendency.annotations


def test_neither_duration_nor_end_given():
    """Test that omitting both `duration` and `end` makes the tendency stop at its
    last time point."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5])
    assert tendency.end == 4
    assert tendency.duration == 4
    assert not tendency.annotations

    _, values = tendency.get_value(np.array([0, 1, 2, 3, 4]))
    assert list(values) == [1, 1, 3, 3, 5]


def test_end_not_after_last_time():
    """Test invalid end and duration values."""
    tendency = StepsTendency(user_time=[0, 10], user_value=[1, 2], user_end=10)
    assert tendency.annotations

    tendency = StepsTendency(user_time=[0, 10], user_value=[1, 2], user_end=5)
    assert tendency.annotations

    tendency = StepsTendency(user_time=[0, 10], user_value=[1, 2], user_duration=5)
    assert tendency.annotations


def test_mismatched_lengths():
    """Test that time and value arrays must have the same length."""
    tendency = StepsTendency(user_time=[0, 10, 20], user_value=[1, 2], user_end=30)
    assert tendency.annotations


def test_empty_arrays():
    """Test that time and value arrays must contain at least one element."""
    tendency = StepsTendency(user_time=[], user_value=[], user_end=10)
    assert tendency.annotations


def test_non_monotonic_time():
    """Test that the time array must be monotonically increasing."""
    tendency = StepsTendency(user_time=[0, 10, 5], user_value=[1, 2, 3], user_end=20)
    assert tendency.annotations

    tendency = StepsTendency(user_time=[0, 10, 10], user_value=[1, 2, 3], user_end=20)
    assert tendency.annotations


def test_start_not_allowed():
    """Test that `start` may not be provided"""
    tendency = StepsTendency(
        user_time=[0, 10], user_value=[1, 2], user_end=20, user_start=5
    )
    assert tendency.annotations


def test_start_and_end_values():
    """Test the start and end values and their derivatives."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_end=6)
    assert tendency.start_value == 1
    assert tendency.end_value == 5
    assert tendency.start_derivative == 0
    assert tendency.end_derivative == 0
    assert not tendency.annotations


def test_generate():
    """Check the generated values."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_end=6)
    time, values = tendency.get_value()
    assert np.all(time == [0, 2, 2, 4, 4, 6])
    assert list(values) == [1, 1, 3, 3, 5, 5]
    assert not tendency.annotations


def test_get_value_at_times():
    """Check the value assignment at arbitrary time points."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_end=6)
    _, values = tendency.get_value(np.array([0, 1, 1.99, 2, 3, 4, 5, 6]))
    assert list(values) == [1, 1, 1, 3, 3, 5, 5, 5]


def test_get_value_outside_bounds():
    """Check the generated values outside of the time array"""
    tendency = StepsTendency(user_time=[1, 2, 3], user_value=[2, 4, 8], user_end=4)
    _, values = tendency.get_value(np.array([-1, 0, 4.5, 5]))
    assert list(values) == [2, 2, 8, 8]


def test_get_derivative():
    """Check that the derivative is always zero."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_end=6)
    derivatives = tendency.get_derivative(np.array([0, 1, 2, 3, 4, 5, 6]))
    assert np.all(derivatives == 0)


@pytest.mark.parametrize("value", [[1, 2, 3], [1.5, 2.5, 3.5], ["a", "b", "c"]])
def test_value_types(value):
    """Test that int, float, and str steps are all supported."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=value, user_end=6)
    assert not tendency.annotations
    assert tendency.value_type is type(value[0])
    assert list(tendency.value) == value
