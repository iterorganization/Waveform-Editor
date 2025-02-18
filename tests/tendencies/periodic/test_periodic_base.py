from unittest.mock import patch

import numpy as np
import pytest
from pytest import approx

from tests.utils import filter_kwargs
from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


@pytest.fixture(autouse=True)
def patch_periodic_base_tendency():
    arr = np.array([0])
    with (
        patch.object(PeriodicBaseTendency, "get_value", return_value=(arr, arr)),
        patch.object(PeriodicBaseTendency, "get_derivative", return_value=arr),
    ):
        yield


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
    kwargs = filter_kwargs(
        user_base=base, user_amplitude=amplitude, user_min=min, user_max=max
    )

    tendency = PeriodicBaseTendency(user_duration=1, **kwargs)
    if has_error:
        assert tendency.annotations
    else:
        assert tendency.base == approx(expected_base)
        assert tendency.amplitude == approx(expected_amplitude)
        assert not tendency.annotations


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
    kwargs = filter_kwargs(
        user_base=base, user_amplitude=amplitude, user_min=min, user_max=max
    )
    tendency = PeriodicBaseTendency(user_duration=1, **kwargs)
    if has_error:
        assert tendency.annotations
    else:
        tendency.set_previous_tendency(prev_tendency)
        assert tendency.base == approx(expected_base)
        assert tendency.amplitude == approx(expected_amplitude)
        assert not tendency.annotations


@pytest.mark.parametrize(
    "base, amplitude, min, max, expected_base",
    [
        # Missing 2 value
        (None, None, 5, 15, 10),
        (None, 5, None, 15, 10),
        (None, 5, 5, None, 10),
        (10, None, None, 15, 10),
        (10, None, 5, None, 10),
        (10, 5, None, None, 10),
        # Missing 3 values
        (10, None, None, None, 10),
        (None, 5, None, None, 0),
        (None, None, 5, None, 0),
        (None, None, None, 15, 0),
        # Missing all values
        (None, None, None, None, 0),
    ],
)
def test_bounds_next(
    base,
    amplitude,
    min,
    max,
    expected_base,
):
    """
    Test the base, amplitude, minimum and maximum values of the periodic base tendency,
    when the tendency has a next tendency.
    """
    next_tendency = ConstantTendency(user_duration=1, user_value=8)
    kwargs = filter_kwargs(
        user_base=base, user_amplitude=amplitude, user_min=min, user_max=max
    )
    tendency = PeriodicBaseTendency(user_duration=1, **kwargs)
    tendency.set_next_tendency(next_tendency)
    assert tendency.base == approx(expected_base)
    assert not tendency.annotations


def test_frequency_and_period():
    """Test if the frequency and period of the tendency are being set correctly."""

    tendency = PeriodicBaseTendency(user_duration=1, user_frequency=5)
    assert tendency.frequency == 5
    assert tendency.period == approx(0.2)
    assert not tendency.annotations

    tendency = PeriodicBaseTendency(user_duration=1, user_period=4)
    assert tendency.period == 4
    assert tendency.frequency == approx(0.25)
    assert not tendency.annotations

    tendency = PeriodicBaseTendency(user_duration=1, user_period=2, user_frequency=0.5)
    assert tendency.period == 2
    assert tendency.frequency == 0.5
    assert not tendency.annotations

    tendency = PeriodicBaseTendency(user_duration=1, user_period=2, user_frequency=2)
    assert tendency.annotations

    tendency = PeriodicBaseTendency(user_duration=1, user_period=0)
    assert tendency.annotations

    tendency = PeriodicBaseTendency(user_duration=1, user_frequency=0)
    assert tendency.annotations


def test_phase():
    """Test if the phase shift of the tendency is being set correctly."""

    tendency = PeriodicBaseTendency(user_duration=1, user_phase=np.pi / 2)
    assert tendency.phase == approx(np.pi / 2)
    assert not tendency.annotations

    tendency = PeriodicBaseTendency(user_duration=1, user_phase=np.pi)
    assert tendency.phase == approx(np.pi)
    assert not tendency.annotations

    tendency = PeriodicBaseTendency(user_duration=1, user_phase=2 * np.pi)
    assert tendency.phase == approx(0)
    assert not tendency.annotations

    tendency = PeriodicBaseTendency(user_duration=1, user_phase=3 * np.pi)
    assert tendency.phase == approx(np.pi)
    assert not tendency.annotations
