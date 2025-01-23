from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.smooth import SmoothTendency


def test_empty():
    """Test value of empty tendency."""
    tendency = SmoothTendency(user_start=0, user_duration=1)
    assert tendency.from_ == 0.0
    assert tendency.to == 0.0
    assert tendency.derivative_start == 0.0
    assert tendency.derivative_end == 0.0


def test_filled_value():
    """Test value of filled tendency."""
    tendency = SmoothTendency(user_start=0, user_duration=1, user_from=1.1, user_to=2.2)
    assert tendency.from_ == 1.1
    assert tendency.to == 2.2
    assert tendency.derivative_start == 0.0
    assert tendency.derivative_end == 0.0


def test_prev_value():
    """Test values of tendency with a previous tendency."""
    prev_tendency = LinearTendency(
        user_start=0, user_duration=1, user_from=10, user_rate=5
    )
    tendency = SmoothTendency(user_duration=1, user_to=10)
    tendency.set_previous_tendency(prev_tendency)
    assert tendency.from_ == 15
    assert tendency.to == 10
    assert tendency.derivative_start == 5
    assert tendency.derivative_end == 0.0
    assert tendency.prev_tendency == prev_tendency
    assert tendency.next_tendency is None


def test_next_value():
    """Test values of tendency with a next tendency."""
    next_tendency = LinearTendency(user_duration=1, user_from=11, user_rate=5)
    tendency = SmoothTendency(user_start=0, user_duration=1, user_from=10)
    tendency.set_next_tendency(next_tendency)
    assert tendency.from_ == 10
    assert tendency.to == 11
    assert tendency.derivative_start == 0.0
    assert tendency.derivative_end == 5
    assert tendency.prev_tendency is None
    assert tendency.next_tendency == next_tendency


def test_prev_and_next_value():
    """Test values of tendency with both a previous and next tendency."""
    prev_tendency = LinearTendency(
        user_start=0, user_duration=1, user_from=10, user_rate=3
    )
    next_tendency = LinearTendency(user_duration=1, user_from=11, user_rate=5)
    tendency = SmoothTendency(user_duration=1)
    tendency.set_next_tendency(next_tendency)
    tendency.set_previous_tendency(prev_tendency)
    assert tendency.from_ == 13
    assert tendency.to == 11
    assert tendency.derivative_start == 3
    assert tendency.derivative_end == 5
    assert tendency.prev_tendency == prev_tendency
    assert tendency.next_tendency == next_tendency


def test_generate():
    """
    Check the generated values.
    """
    tendency = SmoothTendency(user_start=0, user_duration=1, user_from=3, user_to=6)
    _, values = tendency.generate()

    assert values[0] == 3
    assert values[-1] == 6
