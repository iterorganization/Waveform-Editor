import pytest
from pytest import approx

from waveform_editor.tendencies.base import BaseTendency


@pytest.mark.parametrize(
    "start, duration, end, expected_start, expected_duration, expected_end, has_error",
    [
        (10, 20, 30, 10, 20, 30, False),
        (10, 20, None, 10, 20, 30, False),
        (10, None, 30, 10, 20, 30, False),
        (None, 20, 30, 10, 20, 30, False),
        (10, None, None, None, None, None, True),
        (None, 20, None, 0, 20, 20, False),
        (None, None, 30, 0, 30, 30, False),
        (None, None, None, None, None, None, True),
        (10, 20, 40, None, None, None, True),
        (30, None, 10, None, None, None, True),
    ],
)
def test_first_base_tendency(
    start,
    duration,
    end,
    expected_start,
    expected_duration,
    expected_end,
    has_error,
):
    """Test validity of the created base tendency when it is the first tendency."""
    if has_error:
        with pytest.raises(ValueError):
            BaseTendency(start, duration, end)
    else:
        base_tendency = BaseTendency(start, duration, end)
        assert base_tendency.start == approx(expected_start)
        assert base_tendency.duration == approx(expected_duration)
        assert base_tendency.end == approx(expected_end)


@pytest.mark.parametrize(
    "start, duration, end, expected_start, expected_duration, expected_end, has_error",
    [
        (10, 20, 30, 10, 20, 30, False),
        (10, 20, None, 10, 20, 30, False),
        (10, None, 30, 10, 20, 30, False),
        (None, 20, 30, 10, 20, 30, False),
        (10, None, None, None, None, None, True),
        (None, 20, None, 10, 20, 30, False),
        (None, None, 30, 10, 20, 30, False),
        (None, None, None, None, None, None, True),
        (10, 20, 40, None, None, None, True),
        (30, None, 10, None, None, None, True),
    ],
)
def test_second_base_tendency(
    start,
    duration,
    end,
    expected_start,
    expected_duration,
    expected_end,
    has_error,
):
    """Test validity of the created base tendency when it is the second tendency."""
    prev_tendency = BaseTendency(0, 10, 10)

    if has_error:
        with pytest.raises(ValueError):
            BaseTendency(start, duration, end)
    else:
        base_tendency = BaseTendency(start, duration, end)
        base_tendency.set_previous_tendency(prev_tendency)
        assert base_tendency.start == approx(expected_start)
        assert base_tendency.duration == approx(expected_duration)
        assert base_tendency.end == approx(expected_end)
