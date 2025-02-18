import numpy as np
import pytest
from pytest import approx

from tests.utils import filter_kwargs
from waveform_editor.tendencies.linear import LinearTendency


def test_empty():
    """Test values of empty tendency."""
    tendency = LinearTendency(user_start=0, user_duration=1)
    assert tendency.from_ == 0.0
    assert tendency.to == 0.0
    assert tendency.rate == 0.0
    assert not tendency.annotations


@pytest.mark.parametrize(
    "duration, from_, to, rate, expected_from, expected_to, expected_rate, has_error",
    [
        (10, 0, 100, 10, 0, 100, 10, False),
        (20, 100, 50, -2.5, 100, 50, -2.5, False),
        (10, 0, 0, 0, 0, 0, 0, False),
        (0.5, 0, None, 2, 0, 1, 2, False),
        # Missing 1 value
        (10, 0, 100, None, 0, 100, 10, False),
        (10, 0, None, 10, 0, 100, 10, False),
        (10, None, 100, 10, 0, 100, 10, False),
        # Missing 2 values
        (10, None, None, 10, 0, 100, 10, False),
        (10, None, 100, None, 0, 100, 10, False),
        (10, 0, None, None, 0, 0, 0, False),
        # Missing 3 values
        (10, None, None, None, 0, 0, 0, False),
        # Invalid combinations
        (10, 0, 100, -5, None, None, None, True),
        (10, 100, 0, 5, None, None, None, True),
        (10, 50, 100, 0, None, None, None, True),
    ],
)
def test_linear_tendency(
    duration, from_, to, rate, expected_from, expected_to, expected_rate, has_error
):
    """Test values of filled tendency."""
    kwargs = filter_kwargs(
        user_duration=duration, user_from=from_, user_to=to, user_rate=rate
    )

    tendency = LinearTendency(**kwargs)
    if has_error:
        assert tendency.annotations
    else:
        assert tendency.duration == duration
        assert tendency.from_ == approx(expected_from)
        assert tendency.to == approx(expected_to)
        assert tendency.rate == approx(expected_rate)
        assert not tendency.annotations


@pytest.mark.parametrize(
    "duration, from_, to, rate, expected_from, expected_to, expected_rate, has_error",
    [
        (10, 0, 100, 10, 0, 100, 10, False),
        (20, 100, 50, -2.5, 100, 50, -2.5, False),
        (10, 0, 0, 0, 0, 0, 0, False),
        (0.5, 0, None, 2, 0, 1, 2, False),
        # Missing 1 value
        (10, 0, 100, None, 0, 100, 10, False),
        (10, 0, None, 10, 0, 100, 10, False),
        (10, None, 100, 10, 0, 100, 10, False),
        # Missing 2 values
        (10, None, None, 10, 5, 105, 10, False),
        (10, None, 100, None, 5, 100, 9.5, False),
        (10, 0, None, None, 0, 0, 0, False),
        # Missing 3 values
        (10, None, None, None, 5, 5, 0, False),
    ],
)
def test_linear_tendency_with_prev(
    duration, from_, to, rate, expected_from, expected_to, expected_rate, has_error
):
    """Test values of tendency that has a previous tendency."""
    prev_tendency = LinearTendency(user_duration=10, user_from=1, user_to=5)
    kwargs = filter_kwargs(
        user_duration=duration, user_from=from_, user_to=to, user_rate=rate
    )
    tendency = LinearTendency(**kwargs)
    if has_error:
        assert tendency.annotations
    else:
        tendency.set_previous_tendency(prev_tendency)
        assert tendency.duration == duration
        assert tendency.from_ == approx(expected_from)
        assert tendency.to == approx(expected_to)
        assert tendency.rate == approx(expected_rate)
        assert not tendency.annotations


@pytest.mark.parametrize(
    "duration, from_, to, rate, expected_from, expected_to, expected_rate, has_error",
    [
        (10, 0, 100, 10, 0, 100, 10, False),
        (20, 100, 50, -2.5, 100, 50, -2.5, False),
        (10, 0, 0, 0, 0, 0, 0, False),
        (0.5, 0, None, 2, 0, 1, 2, False),
        # Missing 1 value
        (10, 0, 100, None, 0, 100, 10, False),
        (10, 0, None, 10, 0, 100, 10, False),
        (10, None, 100, 10, 0, 100, 10, False),
        # Missing 2 values
        (10, None, None, 10, 0, 100, 10, False),
        (10, None, 10, None, 0, 10, 1, False),
        (10, -5, None, None, -5, 5, 1, False),
        # Missing 3 values
        (10, None, None, None, 0, 5, 0.5, False),
    ],
)
def test_linear_tendency_with_next(
    duration, from_, to, rate, expected_from, expected_to, expected_rate, has_error
):
    """Test values of tendency that has a next tendency."""
    next_tendency = LinearTendency(
        user_start=10, user_duration=10, user_from=5, user_to=10
    )
    kwargs = filter_kwargs(
        user_duration=duration, user_from=from_, user_to=to, user_rate=rate
    )
    tendency = LinearTendency(**kwargs)
    if has_error:
        assert tendency.annotations
    else:
        tendency.set_next_tendency(next_tendency)
        assert tendency.duration == duration
        assert tendency.from_ == approx(expected_from)
        assert tendency.to == approx(expected_to)
        assert tendency.rate == approx(expected_rate)
        assert not tendency.annotations


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = LinearTendency(user_duration=1, user_from=1, user_rate=5)
    assert tendency.start_value == 1
    assert tendency.end_value == 6
    assert tendency.start_derivative == 5
    assert tendency.end_derivative == 5
    assert not tendency.annotations


def test_generate():
    """
    Check the generated values.
    """
    tendency = LinearTendency(user_start=0, user_duration=1, user_from=1, user_to=10)
    time, values = tendency.get_value()
    assert np.all(time == np.array([0, 1]))
    assert np.all(values == np.array([1, 10]))
    assert not tendency.annotations


def test_declarative_assignments():
    t1 = LinearTendency(user_duration=1)
    t2 = LinearTendency(user_duration=1)
    t3 = LinearTendency(user_duration=1)
    t1.set_next_tendency(t2)
    t2.set_next_tendency(t3)
    t3.set_previous_tendency(t2)
    t2.set_previous_tendency(t1)

    assert t1.from_ == t1.to == t2.from_ == t2.to == t3.from_ == t3.to == 0

    t1.user_to = 1
    assert t1.from_ == 0
    assert t1.to == t2.from_ == t2.to == t3.from_ == t3.to == 1

    t3.user_from = 2
    assert t1.from_ == 0
    assert t1.to == t2.from_ == 1
    assert t2.to == t3.from_ == t3.to == 2

    assert not t1.annotations
    assert not t2.annotations
    assert not t3.annotations
