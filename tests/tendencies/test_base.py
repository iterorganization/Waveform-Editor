import numpy as np
import pytest
from pytest import approx

from tests.utils import filter_kwargs
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency


@pytest.mark.parametrize(
    "start, duration, end, expected_start, expected_duration, expected_end, has_error",
    [
        (10, 20, 30, 10, 20, 30, False),
        (10, 20, None, 10, 20, 30, False),
        (10, None, 30, 10, 20, 30, False),
        (None, 20, 30, 10, 20, 30, False),
        (10, None, None, 10, 1, 11, False),
        (None, 20, None, 0, 20, 20, False),
        (None, None, 30, 0, 30, 30, False),
        (None, None, None, 0, 1, 1, False),
        (10, 20, 40, 0, 1, 1, True),
        (10, None, 5, 10, 1, 1, True),
        (10, -5, None, 10, 1, 11, True),
        (None, 0, None, 0, 1, 1, True),
    ],
)
def test_first_tendency(
    start,
    duration,
    end,
    expected_start,
    expected_duration,
    expected_end,
    has_error,
):
    """Test validity of the created base tendency when it is the first tendency."""
    kwargs = filter_kwargs(user_start=start, user_duration=duration, user_end=end)
    tendency = LinearTendency(**kwargs)

    assert tendency.start == approx(expected_start)
    assert tendency.duration == approx(expected_duration)
    assert tendency.end == approx(expected_end)
    if has_error:
        assert tendency.annotations
    else:
        assert not tendency.annotations


@pytest.mark.parametrize(
    "start, duration, end, expected_start, expected_duration, expected_end, has_error",
    [
        (10, 20, 30, 10, 20, 30, False),
        (10, 20, None, 10, 20, 30, False),
        (10, None, 30, 10, 20, 30, False),
        (None, 20, 30, 10, 20, 30, False),
        (10, None, None, 10, 1, 11, False),
        (None, 20, None, 10, 20, 30, False),
        (None, None, 30, 10, 20, 30, False),
        (None, None, None, 10, 1, 11, False),
        (10, 20, 40, 10, 1, 11, True),
        (10, None, 5, 10, 1, 1, True),
        (10, -5, None, 10, 1, 11, True),
        (None, 0, None, 10, 1, 11, True),
    ],
)
def test_second_tendency(
    start,
    duration,
    end,
    expected_start,
    expected_duration,
    expected_end,
    has_error,
):
    """Test validity of the created base tendency when it is the second tendency."""
    prev_tendency = LinearTendency(user_start=0, user_end=10)
    kwargs = filter_kwargs(user_start=start, user_duration=duration, user_end=end)
    tendency = LinearTendency(**kwargs)
    tendency.set_previous_tendency(prev_tendency)
    prev_tendency.set_next_tendency(tendency)

    assert tendency.start == approx(expected_start)
    assert tendency.duration == approx(expected_duration)
    assert tendency.end == approx(expected_end)
    if has_error:
        assert tendency.annotations
    else:
        assert not tendency.annotations


def test_suggestion():
    """Test if suggestions are provided for miswritten keywords."""
    tendency = LinearTendency(user_starrt=0, user_duuration=5, user_ennd=10)
    assert tendency.annotations
    assert tendency.start == 0
    assert tendency.duration == 1
    assert tendency.end == 1
    assert any("start" in annotation["text"] for annotation in tendency.annotations)
    assert any("duration" in annotation["text"] for annotation in tendency.annotations)
    assert any("end" in annotation["text"] for annotation in tendency.annotations)


def test_gap():
    """Test if a gap between 2 tendencies is encountered."""
    t1 = LinearTendency(user_start=0, user_duration=5, user_end=5)
    t2 = LinearTendency(user_start=15, user_duration=5, user_end=20)
    t2.set_previous_tendency(t1)
    t1.set_next_tendency(t2)
    assert not t1.annotations
    assert t2.annotations

    assert t1.start == 0
    assert t1.duration == 5
    assert t1.end == 5

    assert t2.start == 15
    assert t2.duration == 5
    assert t2.end == 20


def test_overlap():
    """Test if an overlap between 2 tendencies is encountered."""
    t1 = LinearTendency(user_start=0, user_duration=5, user_end=5)
    t2 = LinearTendency(user_start=3, user_duration=5, user_end=8)
    t2.set_previous_tendency(t1)
    t1.set_next_tendency(t2)
    assert not t1.annotations
    assert t2.annotations

    assert t1.start == 0
    assert t1.duration == 5
    assert t1.end == 5

    assert t2.start == 3
    assert t2.duration == 5
    assert t2.end == 8


def test_declarative_assignments():
    t1 = LinearTendency(user_duration=10)
    t2 = LinearTendency(user_duration=5)
    t2.set_previous_tendency(t1)

    assert t1.end == approx(10)
    assert t2.end == approx(15)

    t1.user_start = 5
    assert t1.start == approx(5)
    assert t1.end == approx(15)
    assert t2.start == approx(15)
    assert t2.end == approx(20)
    assert not t1.annotations
    assert not t2.annotations


def test_float_error():
    """Don't raise gap annotations when times don't match due to floating point
    precision."""
    t1 = SineWaveTendency(user_duration=1.7)
    t2 = LinearTendency(user_duration=2)
    t2.set_previous_tendency(t1)
    t1.set_next_tendency(t2)

    # t2 starts at 1.7000000000000002 due to floating point precision error
    assert t1.end != t2.start
    assert np.isclose(t1.end, t2.start)
    assert not t1.annotations
    assert not t2.annotations


def test_implicit_start_value():
    """Test if start value matches previous end value."""
    t1 = SineWaveTendency(user_duration=1.75, user_base=8, user_amplitude=2)
    t2 = LinearTendency(user_duration=2, user_to=2)
    t2.set_previous_tendency(t1)
    t1.set_next_tendency(t2)

    assert t1.end_value == 6
    assert t2.start_value == 6
    _, t1_val = t1.get_value([1.75])
    assert t1_val == 6
    _, t2_val = t2.get_value([1.75])
    assert t2_val == 6
