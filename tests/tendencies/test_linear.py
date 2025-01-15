import pytest
from pytest import approx

from waveform_editor.tendencies.linear import LinearTendency


def test_empty():
    """Test values of empty tendency."""
    tendency = LinearTendency(start=0, duration=1)
    assert tendency.from_ == 0.0
    assert tendency.to == 1.0
    assert tendency.rate == 1.0


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
        (10, 0, None, None, 0, 1, 0.1, False),
        # Missing 3 values
        (10, None, None, None, 0, 1, 0.1, False),
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
    if has_error:
        with pytest.raises(ValueError):
            LinearTendency(duration=duration, from_=from_, to=to, rate=rate)
    else:
        tendency = LinearTendency(duration=duration, from_=from_, to=to, rate=rate)
        assert tendency.duration == duration
        assert tendency.from_ == approx(expected_from)
        assert tendency.to == approx(expected_to)
        assert tendency.rate == approx(expected_rate)


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
        (10, 0, None, None, 0, 1, 0.1, False),
        # Missing 3 values
        (10, None, None, None, 5, 1, -0.4, False),
    ],
)
def test_linear_tendency_with_prev(
    duration, from_, to, rate, expected_from, expected_to, expected_rate, has_error
):
    """Test values of tendency that has a previous tendency."""
    prev_tendency = LinearTendency(duration=10, from_=1, to=5)
    if has_error:
        with pytest.raises(ValueError):
            LinearTendency(duration=duration, from_=from_, to=to, rate=rate)
    else:
        tendency = LinearTendency(duration=duration, from_=from_, to=to, rate=rate)
        tendency.set_previous_tendency(prev_tendency)
        assert tendency.duration == duration
        assert tendency.from_ == approx(expected_from)
        assert tendency.to == approx(expected_to)
        assert tendency.rate == approx(expected_rate)


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
        (10, None, None, 10, -95, 5, 10, False),
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
    next_tendency = LinearTendency(start=10, duration=10, from_=5, to=10)
    if has_error:
        with pytest.raises(ValueError):
            LinearTendency(duration=duration, from_=from_, to=to, rate=rate)
    else:
        tendency = LinearTendency(duration=duration, from_=from_, to=to, rate=rate)
        tendency.set_next_tendency(next_tendency)
        assert tendency.duration == duration
        assert tendency.from_ == approx(expected_from)
        assert tendency.to == approx(expected_to)
        assert tendency.rate == approx(expected_rate)
