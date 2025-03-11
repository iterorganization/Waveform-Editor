import numpy as np
import pytest
from pytest import approx

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.repeat import RepeatTendency


@pytest.fixture
def repeat_waveform():
    return {
        "user_duration": 8,
        "user_waveform": [
            {"user_type": "linear", "user_from": 1, "user_to": 2, "user_duration": 1},
            {"user_type": "constant", "user_value": 2, "user_duration": 0.5},
            {
                "user_type": "sine-wave",
                "user_base": 2,
                "user_amplitude": -1,
                "user_frequency": 0.25,
                "user_duration": 1,
            },
        ],
    }


def assert_no_annotations(repeat_tendency):
    """Test if neither the repeat tendency nor the underlying repeated tendencies have
    annotations."""
    assert not repeat_tendency.annotations
    for tendency in repeat_tendency.waveform.tendencies:
        assert not tendency.annotations


def test_repeat_loop():
    """Test if repeat tendency correctly links first and last tendencies."""
    looped_waveform = {
        "user_duration": 8,
        "user_waveform": [
            {"user_type": "linear", "user_from": 1, "user_to": 2, "user_duration": 2},
            {"user_type": "linear", "user_from": 2, "user_to": -1, "user_duration": 1},
            {"user_type": "linear", "user_duration": 1},
        ],
    }
    repeat_tendency = RepeatTendency(**looped_waveform)
    times = np.linspace(0, 8, 17)
    _, values = repeat_tendency.get_value(times)
    check_values_at_times([0, 4, 8], times, values, 1)
    check_values_at_times([2, 6], times, values, 2)
    check_values_at_times([3, 7], times, values, -1)
    check_values_at_times([3.5, 7.5], times, values, 0)
    assert_no_annotations(repeat_tendency)


def test_smooth_loop():
    """Test if repeat tendency correctly links the last smooth tendency to the first."""
    looped_waveform = {
        "user_duration": 8,
        "user_waveform": [
            {"user_type": "linear", "user_from": 1, "user_to": 2, "user_duration": 2},
            {"user_type": "linear", "user_from": 2, "user_to": -1, "user_duration": 1},
            {"user_type": "smooth", "user_duration": 1},
        ],
    }
    repeat_tendency = RepeatTendency(**looped_waveform)
    assert repeat_tendency.waveform.tendencies[-1].from_ == -1
    assert repeat_tendency.waveform.tendencies[-1].to == 1
    assert_no_annotations(repeat_tendency)


def test_single_tendency():
    """Test if a repeated tendency with a single tendency works."""
    looped_waveform = {
        "user_duration": 4,
        "user_waveform": [
            {"user_type": "linear", "user_from": 1, "user_to": 2, "user_duration": 3},
        ],
    }
    repeat_tendency = RepeatTendency(**looped_waveform)
    assert repeat_tendency.waveform.tendencies[0].start == 0
    assert repeat_tendency.waveform.tendencies[0].end == 3
    assert repeat_tendency.waveform.tendencies[0].from_ == 1
    assert repeat_tendency.waveform.tendencies[0].to == 2
    assert_no_annotations(repeat_tendency)

    looped_waveform = {
        "user_duration": 4,
        "user_waveform": [
            {"user_type": "linear", "user_duration": 3},
        ],
    }
    repeat_tendency = RepeatTendency(**looped_waveform)
    assert repeat_tendency.waveform.tendencies[0].start == 0
    assert repeat_tendency.waveform.tendencies[0].end == 3
    assert repeat_tendency.waveform.tendencies[0].from_ == 0
    assert repeat_tendency.waveform.tendencies[0].to == 0
    assert_no_annotations(repeat_tendency)


def test_zero_start(repeat_waveform):
    """Test if zero start does not raise an error."""
    repeat_waveform["user_waveform"][0]["user_start"] = 0
    repeat_tendency = RepeatTendency(**repeat_waveform)
    assert_no_annotations(repeat_tendency)


def test_one_start(repeat_waveform):
    """Test if non-zero start raises an error."""
    repeat_waveform["user_waveform"][0]["user_start"] = 1
    repeat_tendency = RepeatTendency(**repeat_waveform)
    assert repeat_tendency.annotations


def test_empty():
    """Test if ill-defined tendency raises an error."""
    repeat_tendency = RepeatTendency()
    assert repeat_tendency.annotations

    repeat_tendency = RepeatTendency(user_duration=8)
    assert repeat_tendency.annotations


def check_values_at_times(target_times, times, values, expected_value):
    """Helper function to check values at specific times."""
    for target_time in target_times:
        closest_index = min(
            range(len(times)), key=lambda i: abs(times[i] - target_time)
        )
        closest_value = values[closest_index]
        assert closest_value == approx(expected_value)


def test_repeated_values(repeat_waveform):
    """Test if generated values are correct."""
    repeat_tendency = RepeatTendency(**repeat_waveform)
    times = np.linspace(0, 8, 17)
    _, values = repeat_tendency.get_value(times)
    check_values_at_times([0, 2.5, 5, 7.5], times, values, 1)
    check_values_at_times([0.5, 3, 5.5, 8], times, values, 1.5)
    check_values_at_times([1, 3.5, 6], times, values, 2)
    check_values_at_times([1.5, 4, 6.5], times, values, 2)
    check_values_at_times([2.0, 4.5, 7], times, values, 2 - np.sin(np.pi / 4))
    assert_no_annotations(repeat_tendency)


def test_filled(repeat_waveform):
    """Test if tendencies in repeated waveform are filled correctly."""

    repeat_tendency = RepeatTendency(**repeat_waveform)
    assert not repeat_tendency.annotations
    tendencies = repeat_tendency.waveform.tendencies
    assert isinstance(tendencies[0], LinearTendency)
    assert tendencies[0].start == 0
    assert tendencies[0].end == 1
    assert tendencies[0].from_ == 1
    assert tendencies[0].to == 2
    assert isinstance(tendencies[1], ConstantTendency)
    assert tendencies[1].start == 1
    assert tendencies[1].end == 1.5
    assert tendencies[1].value == 2
    assert isinstance(tendencies[2], SineWaveTendency)
    assert tendencies[2].start == 1.5
    assert tendencies[2].end == 2.5
    assert tendencies[2].base == 2
    assert tendencies[2].amplitude == -1
    assert tendencies[2].frequency == 0.25


def test_too_short(repeat_waveform):
    """Check for warning in annotations if repeated waveform has not completed a
    single repetition."""
    repeat_waveform["user_duration"] = 2
    repeat_tendency = RepeatTendency(**repeat_waveform)
    assert repeat_tendency.annotations
    assert repeat_tendency.annotations[0]["type"] == "warning"


def test_period(repeat_waveform):
    """Check values when period is provided."""
    repeat_waveform["user_period"] = 1
    repeat_tendency = RepeatTendency(**repeat_waveform)
    times = np.linspace(0, 8, 33)

    _, values = repeat_tendency.get_value(times)
    check_values_at_times(np.arange(0, 9), times, values, 1)
    check_values_at_times(np.arange(0.25, 8, 1), times, values, 1.625)
    check_values_at_times(np.arange(0.5, 8.5, 1), times, values, 2)
    check_values_at_times(
        np.arange(0.75, 8, 1), times, values, 2 - np.sin(np.pi * 3 / 16)
    )
