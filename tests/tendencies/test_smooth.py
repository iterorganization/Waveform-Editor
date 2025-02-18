from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.smooth import SmoothTendency


def test_empty():
    """Test value of empty tendency."""
    tendency = SmoothTendency(user_start=0, user_duration=1)
    assert tendency.from_ == 0.0
    assert tendency.to == 0.0
    assert tendency.start_derivative == 0.0
    assert tendency.end_derivative == 0.0
    assert not tendency.annotations


def test_filled_value():
    """Test value of filled tendency."""
    tendency = SmoothTendency(user_start=0, user_duration=1, user_from=1.1, user_to=2.2)
    assert tendency.from_ == 1.1
    assert tendency.to == 2.2
    assert tendency.start_derivative == 0.0
    assert tendency.end_derivative == 0.0
    assert not tendency.annotations


def test_prev_value():
    """Test values of tendency with a previous tendency."""
    prev_tendency = LinearTendency(
        user_start=0, user_duration=1, user_from=10, user_rate=5
    )
    tendency = SmoothTendency(user_duration=1, user_to=10)
    tendency.set_previous_tendency(prev_tendency)
    assert tendency.from_ == 15
    assert tendency.to == 10
    assert tendency.start_derivative == 5
    assert tendency.end_derivative == 0.0
    assert tendency.prev_tendency == prev_tendency
    assert tendency.next_tendency is None
    assert not tendency.annotations


def test_next_value():
    """Test values of tendency with a next tendency."""
    next_tendency = LinearTendency(user_duration=1, user_from=11, user_rate=5)
    tendency = SmoothTendency(user_start=0, user_duration=1, user_from=10)
    tendency.set_next_tendency(next_tendency)
    next_tendency.set_previous_tendency(tendency)
    assert tendency.from_ == 10
    assert tendency.to == 11
    assert tendency.start_derivative == 0.0
    assert tendency.end_derivative == 5
    assert tendency.prev_tendency is None
    assert tendency.next_tendency == next_tendency
    assert not tendency.annotations


def test_prev_and_next_value():
    """Test values of tendency with both a previous and next tendency."""
    prev_tendency = LinearTendency(
        user_start=0, user_duration=1, user_from=10, user_rate=3
    )
    next_tendency = LinearTendency(user_duration=1, user_from=11, user_rate=5)
    tendency = SmoothTendency(user_duration=1)
    tendency.set_next_tendency(next_tendency)
    prev_tendency.set_next_tendency(tendency)
    tendency.set_previous_tendency(prev_tendency)
    next_tendency.set_previous_tendency(tendency)
    assert tendency.from_ == 13
    assert tendency.to == 11
    assert tendency.start_derivative == 3
    assert tendency.end_derivative == 5
    assert tendency.prev_tendency == prev_tendency
    assert tendency.next_tendency == next_tendency
    assert not tendency.annotations


def test_get_value():
    """
    Check the generated values.
    """
    tendency = SmoothTendency(user_start=0, user_duration=1, user_from=3, user_to=6)
    _, values = tendency.get_value()

    assert values[0] == 3
    assert values[-1] == 6
    assert not tendency.annotations


def test_get_value_no_start():
    """
    Check the generated values when no start is provided.
    """
    tendency = SmoothTendency(user_duration=8, user_from=3, user_to=6)
    _, values = tendency.get_value()

    assert values[0] == 3
    assert values[-1] == 6
    assert not tendency.annotations
