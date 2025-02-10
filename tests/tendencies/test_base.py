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
        # (10, None, None, None, None, None, True),
        (None, 20, None, 0, 20, 20, False),
        (None, None, 30, 0, 30, 30, False),
        # (None, None, None, None, None, None, True),
        (10, 20, 40, None, None, None, True),
        # (30, None, 10, None, None, None, True),
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
    kwargs = dict(user_start=start, user_duration=duration, user_end=end)
    base_tendency = BaseTendency(**kwargs)

    if has_error:
        assert base_tendency.annotations.get()
    else:
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
        # (10, None, None, None, None, None, True),
        (None, 20, None, 10, 20, 30, False),
        (None, None, 30, 10, 20, 30, False),
        # (None, None, None, None, None, None, True),
        (10, 20, 40, None, None, None, True),
        # (30, None, 10, None, None, None, True),
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
    prev_tendency = BaseTendency(user_start=0, user_end=10)
    kwargs = dict(user_start=start, user_duration=duration, user_end=end)
    base_tendency = BaseTendency(**kwargs)

    if has_error:
        assert base_tendency.annotations.get()
    else:
        base_tendency.set_previous_tendency(prev_tendency)
        assert base_tendency.start == approx(expected_start)
        assert base_tendency.duration == approx(expected_duration)
        assert base_tendency.end == approx(expected_end)


def test_declarative_assignments():
    t1 = BaseTendency(user_duration=10)
    t2 = BaseTendency(user_duration=5)
    t2.set_previous_tendency(t1)

    assert t1.end == approx(10)
    assert t2.end == approx(15)

    t1.user_start = 5
    assert t1.start == approx(5)
    assert t1.end == approx(15)
    assert t2.start == approx(15)
    assert t2.end == approx(20)
