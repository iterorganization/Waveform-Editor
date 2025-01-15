from waveform_editor.tendencies.constant import ConstantTendency


def test_empty():
    """Test value of empty tendency."""
    tendency = ConstantTendency(start=0, duration=1)
    assert tendency.value == 0.0


def test_filled_value():
    """Test value of filled tendency."""
    tendency = ConstantTendency(start=0, duration=1, value=12.34)
    assert tendency.value == 12.34


def test_prev_value():
    """Test value of empty tendency with a previous tendency."""
    prev_tendency = ConstantTendency(value=12.34, start=0, duration=1)
    tendency = ConstantTendency(duration=1)
    tendency.set_previous_tendency(prev_tendency)
    assert tendency.start == 1
    assert tendency.duration == 1
    assert tendency.end == 2
    assert tendency.value == 12.34
    assert tendency.prev_tendency == prev_tendency
    assert tendency.next_tendency is None


def test_next_value():
    """Test value of empty tendency with a next tendency."""
    next_tendency = ConstantTendency(value=12.34, start=1, duration=1)
    tendency = ConstantTendency(duration=1)
    tendency.set_next_tendency(next_tendency)
    assert tendency.start == 0
    assert tendency.duration == 1
    assert tendency.end == 1
    assert tendency.value == 12.34
    assert tendency.prev_tendency is None
    assert tendency.next_tendency == next_tendency
