import numpy as np
import pytest
from pytest import approx

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


@pytest.mark.parametrize(
    "base, amplitude, min, max, expected_base, expected_amplitude, has_error",
    [
        # All values, overdetermined
        (10, 5, 5, 15, None, None, True),
        # Missing 1 value, overdetermined
        (None, 5, 5, 15, None, None, True),
        (10, None, 5, 15, None, None, True),
        (10, 5, None, 15, None, None, True),
        (10, 5, 5, None, None, None, True),
        # Missing 2 value
        (None, None, 5, 15, 10, 5, False),
        (None, 5, None, 15, 10, 5, False),
        (None, 5, 5, None, 10, 5, False),
        (10, None, None, 15, 10, 5, False),
        (10, None, 5, None, 10, 5, False),
        (10, 5, None, None, 10, 5, False),
        # Missing 3 values
        (10, None, None, None, 10, 0, False),
        (None, 5, None, None, 0, 5, False),
        (None, None, 5, None, 0, -5, False),
        (None, None, None, 15, 0, 15, False),
        # Missing all values
        (None, None, None, None, 0, 0, False),
    ],
)
def test_bounds(
    base,
    amplitude,
    min,
    max,
    expected_base,
    expected_amplitude,
    has_error,
):
    """
    Test the base, amplitude, minimum and maximum values of the periodic base tendency
    """
    tendency = PeriodicBaseTendency(
        user_duration=1,
        user_base=base,
        user_amplitude=amplitude,
        user_min=min,
        user_max=max,
    )
    if has_error:
        assert tendency.value_error is not None
    else:
        assert tendency.base == approx(expected_base)
        assert tendency.amplitude == approx(expected_amplitude)


@pytest.mark.parametrize(
    "base, amplitude, min, max, expected_base, expected_amplitude, has_error",
    [
        # Missing 2 value
        (None, None, 5, 15, 10, 5, False),
        (None, 5, None, 15, 10, 5, False),
        (None, 5, 5, None, 10, 5, False),
        (10, None, None, 15, 10, 5, False),
        (10, None, 5, None, 10, 5, False),
        (10, 5, None, None, 10, 5, False),
        # Missing 3 values
        (10, None, None, None, 10, 0, False),
        (None, 5, None, None, 8, 5, False),
        (None, None, 5, None, 8, 3, False),
        (None, None, None, 15, 8, 7, False),
        # Missing all values
        (None, None, None, None, 8, 0, False),
    ],
)
def test_bounds_prev(
    base,
    amplitude,
    min,
    max,
    expected_base,
    expected_amplitude,
    has_error,
):
    """
    Test the base, amplitude, minimum and maximum values of the periodic base tendency,
    when the tendency has a previous tendency.
    """
    prev_tendency = ConstantTendency(user_start=0, user_duration=1, user_value=8)
    if has_error:
        with pytest.raises(ValueError):
            PeriodicBaseTendency(
                user_duration=1,
                user_base=base,
                user_amplitude=amplitude,
                user_min=min,
                user_max=max,
            )
    else:
        tendency = PeriodicBaseTendency(
            user_duration=1,
            user_base=base,
            user_amplitude=amplitude,
            user_min=min,
            user_max=max,
        )
        tendency.set_previous_tendency(prev_tendency)
        assert tendency.base == approx(expected_base)
        assert tendency.amplitude == approx(expected_amplitude)


@pytest.mark.parametrize(
    "base, amplitude, min, max, expected_base, expected_amplitude, has_error",
    [
        # Missing 2 value
        (None, None, 5, 15, 10, 5, False),
        (None, 5, None, 15, 10, 5, False),
        (None, 5, 5, None, 10, 5, False),
        (10, None, None, 15, 10, 5, False),
        (10, None, 5, None, 10, 5, False),
        (10, 5, None, None, 10, 5, False),
        # Missing 3 values
        (10, None, None, None, 10, 0, False),
        (None, 5, None, None, 0, 5, False),
        (None, None, 5, None, 0, -5, False),
        (None, None, None, 15, 0, 15, False),
        # Missing all values
        (None, None, None, None, 0, 1, False),
    ],
)
def test_bounds_next(
    base,
    amplitude,
    min,
    max,
    expected_base,
    expected_amplitude,
    has_error,
):
    """
    Test the base, amplitude, minimum and maximum values of the periodic base tendency,
    when the tendency has a next tendency.
    """
    next_tendency = ConstantTendency(user_duration=1, user_value=8)
    if has_error:
        with pytest.raises(ValueError):
            PeriodicBaseTendency(
                user_duration=1,
                user_base=base,
                user_amplitude=amplitude,
                user_min=min,
                user_max=max,
            )
    else:
        tendency = PeriodicBaseTendency(
            user_duration=1,
            user_base=base,
            user_amplitude=amplitude,
            user_min=min,
            user_max=max,
        )
        tendency.set_next_tendency(next_tendency)
        assert tendency.base == approx(expected_base)


def test_frequency_and_period():
    """Test if the frequency and period of the tendency are being set correctly."""

    tendency = PeriodicBaseTendency(user_duration=1, user_frequency=5)
    assert tendency.frequency == 5
    assert tendency.period == approx(0.2)

    tendency = PeriodicBaseTendency(user_duration=1, user_period=4)
    assert tendency.period == 4
    assert tendency.frequency == approx(0.25)

    tendency = PeriodicBaseTendency(user_duration=1, user_period=2, user_frequency=0.5)
    assert tendency.period == 2
    assert tendency.frequency == 0.5

    tendency = PeriodicBaseTendency(user_duration=1, user_period=2, user_frequency=2)
    assert tendency.value_error is not None

    with pytest.raises(ValueError):
        tendency = PeriodicBaseTendency(user_duration=1, user_period=0)

    with pytest.raises(ValueError):
        tendency = PeriodicBaseTendency(user_duration=1, user_frequency=0)


def test_phase():
    """Test if the phase shift of the tendency is being set correctly."""

    tendency = PeriodicBaseTendency(user_duration=1, user_phase=np.pi / 2)
    assert tendency.phase == approx(np.pi / 2)

    tendency = PeriodicBaseTendency(user_duration=1, user_phase=np.pi)
    assert tendency.phase == approx(np.pi)

    tendency = PeriodicBaseTendency(user_duration=1, user_phase=2 * np.pi)
    assert tendency.phase == approx(0)

    tendency = PeriodicBaseTendency(user_duration=1, user_phase=3 * np.pi)
    assert tendency.phase == approx(np.pi)
