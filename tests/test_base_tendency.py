import numpy as np
import pytest

from waveform_editor.tendencies.base_tendency import BaseTendency, TimeInterval


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
    time_interval = TimeInterval(start=start, duration=duration, end=end)
    if has_error:
        with pytest.raises(ValueError):
            BaseTendency(time_interval)
    else:
        base_tendency = BaseTendency(time_interval)
        assert np.isclose(
            base_tendency.start, expected_start
        ), f"Expected start {expected_start}, got {base_tendency.start}"
        assert np.isclose(
            base_tendency.duration, expected_duration
        ), f"Expected duration {expected_duration}, got {base_tendency.duration}"
        assert np.isclose(
            base_tendency.end, expected_end
        ), f"Expected end {expected_end}, got {base_tendency.end}"


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
    prev_time_interval = TimeInterval(start=0, duration=10, end=10)
    prev_tendency = BaseTendency(prev_time_interval)

    time_interval = TimeInterval(start=start, duration=duration, end=end)
    if has_error:
        with pytest.raises(ValueError):
            BaseTendency(time_interval)
    else:
        base_tendency = BaseTendency(time_interval)
        base_tendency.set_previous_tendency(prev_tendency)
        prev_tendency.set_previous_tendency(base_tendency)
        assert np.isclose(
            base_tendency.start, expected_start
        ), f"Expected start {expected_start}, got {base_tendency.start}"
        assert np.isclose(
            base_tendency.duration, expected_duration
        ), f"Expected duration {expected_duration}, got {base_tendency.duration}"
        assert np.isclose(
            base_tendency.end, expected_end
        ), f"Expected end {expected_end}, got {base_tendency.end}"
