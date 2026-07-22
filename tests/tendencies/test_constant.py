import numpy as np

from waveform_editor.tendencies.constant import ConstantTendency


def test_empty():
    """Test value of empty tendency."""
    tendency = ConstantTendency(user_start=0, user_duration=1)
    assert tendency.value == 0.0
    assert not tendency.annotations


def test_filled_value():
    """Test value of filled tendency."""
    tendency = ConstantTendency(user_start=0, user_duration=1, user_value=12.34)
    assert tendency.value == 12.34
    assert not tendency.annotations


def test_prev_value():
    """Test value of empty tendency with a previous tendency."""
    prev_tendency = ConstantTendency(user_value=12.34, user_start=0, user_duration=1)
    tendency = ConstantTendency(user_duration=1)
    tendency.set_previous_tendency(prev_tendency)
    assert tendency.start == 1
    assert tendency.duration == 1
    assert tendency.end == 2
    assert tendency.value == 12.34
    assert tendency.prev_tendency is prev_tendency
    assert tendency.next_tendency is None
    assert not tendency.annotations


def test_next_value():
    """Test value of empty tendency with a next tendency."""
    next_tendency = ConstantTendency(user_value=12.34, user_start=1, user_duration=1)
    tendency = ConstantTendency(user_duration=1)
    tendency.set_next_tendency(next_tendency)
    assert tendency.start == 0
    assert tendency.duration == 1
    assert tendency.end == 1
    assert tendency.value == 0
    assert tendency.prev_tendency is None
    assert tendency.next_tendency is next_tendency
    assert not tendency.annotations


def test_start_and_end():
    """
    Test the start and end values and their derivatives
    """
    tendency = ConstantTendency(user_duration=1, user_value=5)
    assert tendency.start_value == 5
    assert tendency.end_value == 5
    assert tendency.start_derivative == 0
    assert tendency.end_derivative == 0
    assert not tendency.annotations


def test_generate():
    """
    Check the generated values.
    """
    tendency = ConstantTendency(user_start=0, user_duration=1, user_value=5)
    time, values = tendency.get_value()

    assert np.all(time == np.array([0, 1]))
    assert np.all(values == np.array([5, 5]))
    assert not tendency.annotations


def test_categorical_string_value():
    tendency = ConstantTendency(user_start=0, user_duration=1, user_value="ec")
    assert tendency.value == "ec"
    assert tendency.value_type is str
    assert not tendency.annotations

    time, values = tendency.get_value()
    assert np.all(time == np.array([0, 1]))
    assert list(values) == ["ec", "ec"]


def test_categorical_bool_value():
    tendency = ConstantTendency(user_start=0, user_duration=1, user_value=True)
    assert tendency.value is True
    assert tendency.value_type is bool
    assert not tendency.annotations

    time, values = tendency.get_value()
    assert np.all(time == np.array([0, 1]))
    assert list(values) == [True, True]


def test_categorical_int_value():
    tendency = ConstantTendency(user_start=0, user_duration=1, user_value=3)
    assert tendency.value == 3
    assert tendency.value_type is int
    assert not tendency.annotations

    time, values = tendency.get_value()
    assert np.all(time == np.array([0, 1]))
    assert list(values) == [3, 3]


def test_declarative_assignments():
    t1 = ConstantTendency(user_duration=1)
    t2 = ConstantTendency(user_duration=1)
    t2.set_previous_tendency(t1)

    assert t1.value == 0
    assert t2.value == 0

    t1.user_value = 5
    assert t1.value == 5
    assert t2.value == 5

    t2.user_value = 6
    assert t1.value == 5
    assert t2.value == 6
    assert not t1.annotations
    assert not t2.annotations
