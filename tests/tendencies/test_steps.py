import numpy as np

from waveform_editor.tendencies.steps import StepsTendency
from waveform_editor.waveform import Waveform


def test_filled():
    """Time/value arrays keep their native dtype and are not interpolated."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5])
    assert np.all(tendency.time == np.array([0, 2, 4]))
    assert np.all(tendency.value == np.array([1, 3, 5]))
    assert not tendency.is_categorical
    assert not tendency.annotations


def test_zero_order_hold():
    """Each value is held from its breakpoint until the next; ends extrapolate."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5])
    t = np.array([-1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    _, values = tendency.get_value(t)
    assert list(values) == [1, 1, 1, 3, 3, 5, 5]


def test_derivative_is_zero():
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5])
    assert np.all(tendency.get_derivative(np.array([0.0, 1.0, 2.0, 3.0])) == 0)


def test_string_values():
    """A steps tendency can hold string values."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=["ohmic", "nbi", "ec"])
    assert tendency.is_categorical
    _, values = tendency.get_value(np.array([0.0, 1.0, 2.0, 3.0, 4.0]))
    assert list(values) == ["ohmic", "ohmic", "nbi", "nbi", "ec"]
    assert not tendency.annotations


def test_boolean_values():
    """A steps tendency can hold boolean values, which are categorical (held)."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[False, True, False])
    assert tendency.is_categorical
    _, values = tendency.get_value(np.array([0.0, 1.0, 2.0, 3.0, 4.0]))
    assert [bool(v) for v in values] == [False, False, True, True, False]
    assert not tendency.annotations


def test_non_monotonic_time():
    tendency = StepsTendency(user_time=[0, 2, 1], user_value=[1, 2, 3])
    assert tendency.annotations


def test_mismatched_lengths():
    tendency = StepsTendency(user_time=[0, 2], user_value=[1, 2, 3])
    assert tendency.annotations


def test_start_and_end_inference():
    """Start comes from the first breakpoint; end defaults to the last breakpoint."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5])
    assert tendency.start == 0
    assert tendency.end == 4


def test_explicit_end_holds_final_value():
    """An explicit end holds the final value for its full duration."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_end=6)
    assert tendency.start == 0
    assert tendency.end == 6
    assert not tendency.annotations
    _, values = tendency.get_value(np.array([4.0, 5.0, 6.0]))
    assert list(values) == [5, 5, 5]


def test_end_before_last_time_is_flagged():
    """An end that precedes the last breakpoint is an error."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_end=3)
    assert tendency.annotations


def test_start_not_allowed():
    """Providing an explicit start is rejected; it is inferred from the time list."""
    tendency = StepsTendency(user_time=[0, 2, 4], user_value=[1, 3, 5], user_start=1)
    assert tendency.annotations
    assert tendency.start == 0


def test_in_waveform():
    """A steps tendency drives a zero-order-hold waveform (numeric and string)."""
    numeric = Waveform(
        waveform=[
            {"user_type": "steps", "user_time": [0, 2, 4], "user_value": [1, 3, 5]}
        ]
    )
    assert not numeric.is_categorical
    _, values = numeric.get_value(np.array([0.0, 1.0, 2.0, 3.0, 4.0]))
    assert list(values) == [1, 1, 3, 3, 5]

    string = Waveform(
        waveform=[
            {
                "user_type": "steps",
                "user_time": [0, 2, 4],
                "user_value": ["a", "b", "c"],
            }
        ]
    )
    assert string.is_categorical
    _, values = string.get_value(np.array([1.0, 3.0, 5.0]))
    assert list(values) == ["a", "b", "c"]
