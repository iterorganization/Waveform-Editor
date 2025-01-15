from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.smooth import SmoothTendency


def test_empty():
    """Test value of empty tendency."""
    tendency = SmoothTendency(start=0, duration=1)
    assert tendency.from_ == 0.0
    assert tendency.to == 1.0
    assert tendency.derivative_start == 0.0
    assert tendency.derivative_end == 0.0


def test_filled_value():
    """Test value of filled tendency."""
    tendency = SmoothTendency(start=0, duration=1, from_=1.1, to=2.2)
    assert tendency.from_ == 1.1
    assert tendency.to == 2.2
    assert tendency.derivative_start == 0.0
    assert tendency.derivative_end == 0.0


def test_prev_value():
    """Test values of tendency with a previous tendency."""
    prev_tendency = LinearTendency(start=0, duration=1, from_=10, rate=5)
    tendency = SmoothTendency(duration=1, to=10)
    tendency.set_previous_tendency(prev_tendency)
    assert tendency.from_ == 15
    assert tendency.to == 10
    assert tendency.derivative_start == 5
    assert tendency.derivative_end == 0.0
    assert tendency.prev_tendency == prev_tendency
    assert tendency.next_tendency is None


def test_next_value():
    """Test values of tendency with a next tendency."""
    next_tendency = LinearTendency(duration=1, from_=11, rate=5)
    tendency = SmoothTendency(start=0, duration=1, from_=10)
    tendency.set_next_tendency(next_tendency)
    assert tendency.from_ == 10
    assert tendency.to == 11
    assert tendency.derivative_start == 0.0
    assert tendency.derivative_end == 5
    assert tendency.prev_tendency is None
    assert tendency.next_tendency == next_tendency


def test_prev_and_next_value():
    """Test values of tendency with both a previous and next tendency."""
    prev_tendency = LinearTendency(start=0, duration=1, from_=10, rate=3)
    next_tendency = LinearTendency(duration=1, from_=11, rate=5)
    tendency = SmoothTendency(duration=1)
    tendency.set_next_tendency(next_tendency)
    tendency.set_previous_tendency(prev_tendency)
    assert tendency.from_ == 13
    assert tendency.to == 11
    assert tendency.derivative_start == 3
    assert tendency.derivative_end == 5
    assert tendency.prev_tendency == prev_tendency
    assert tendency.next_tendency == next_tendency
