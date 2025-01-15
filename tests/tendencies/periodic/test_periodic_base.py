import pytest
from pytest import approx

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


@pytest.mark.parametrize(
    "base, amplitude, min, max, expected_base, expected_amplitude, \
    expected_min, expected_max, has_error",
    [
        # All values, overdetermined
        (10, 5, 5, 15, None, None, None, None, True),
        # Missing 1 value, overdetermined
        (None, 5, 5, 15, None, None, None, None, True),
        (10, None, 5, 15, None, None, None, None, True),
        (10, 5, None, 15, None, None, None, None, True),
        (10, 5, 5, None, None, None, None, None, True),
        # Missing 2 value
        (None, None, 5, 15, 10, 5, 5, 15, False),
        (None, 5, None, 15, 10, 5, 5, 15, False),
        (None, 5, 5, None, 10, 5, 5, 15, False),
        (10, None, None, 15, 10, 5, 5, 15, False),
        (10, None, 5, None, 10, 5, 5, 15, False),
        (10, 5, None, None, 10, 5, 5, 15, False),
        # Missing 3 values
        (10, None, None, None, 10, 1, 9, 11, False),
        (None, 5, None, None, 0, 5, -5, 5, False),
        (None, None, 5, None, 6, 1, 5, 7, False),
        (None, None, None, 15, 14, 1, 13, 15, False),
        # Missing all values
        (None, None, None, None, 0, 1, -1, 1, False),
    ],
)
def test_bounds(
    base,
    amplitude,
    min,
    max,
    expected_base,
    expected_amplitude,
    expected_min,
    expected_max,
    has_error,
):
    """
    Test the base, amplitude, minimum and maximum values of the periodic base tendency
    """
    if has_error:
        with pytest.raises(ValueError):
            PeriodicBaseTendency(
                duration=1, base=base, amplitude=amplitude, min=min, max=max
            )
    else:
        tendency = PeriodicBaseTendency(
            duration=1, base=base, amplitude=amplitude, min=min, max=max
        )
        assert tendency.base == approx(expected_base)
        assert tendency.amplitude == approx(expected_amplitude)
        assert tendency.min == approx(expected_min)
        assert tendency.max == approx(expected_max)


@pytest.mark.parametrize(
    "base, amplitude, min, max, expected_base, expected_amplitude, \
    expected_min, expected_max, has_error",
    [
        # Missing 2 value
        (None, None, 5, 15, 10, 5, 5, 15, False),
        (None, 5, None, 15, 10, 5, 5, 15, False),
        (None, 5, 5, None, 10, 5, 5, 15, False),
        (10, None, None, 15, 10, 5, 5, 15, False),
        (10, None, 5, None, 10, 5, 5, 15, False),
        (10, 5, None, None, 10, 5, 5, 15, False),
        # Missing 3 values
        (10, None, None, None, 10, 1, 9, 11, False),
        (None, 5, None, None, 8, 5, 3, 13, False),
        (None, None, 5, None, 8, 3, 5, 11, False),
        (None, None, None, 15, 8, 7, 1, 15, False),
        # Missing all values
        (None, None, None, None, 0, 1, -1, 1, False),
    ],
)
def test_bounds_prev(
    base,
    amplitude,
    min,
    max,
    expected_base,
    expected_amplitude,
    expected_min,
    expected_max,
    has_error,
):
    """
    Test the base, amplitude, minimum and maximum values of the periodic base tendency,
    when the tendency has a previous tendency.
    """
    prev_tendency = ConstantTendency(start=0, duration=1, value=8)
    if has_error:
        with pytest.raises(ValueError):
            PeriodicBaseTendency(
                duration=1, base=base, amplitude=amplitude, min=min, max=max
            )
    else:
        tendency = PeriodicBaseTendency(
            duration=1, base=base, amplitude=amplitude, min=min, max=max
        )
        tendency.set_previous_tendency(prev_tendency)
        assert tendency.base == approx(expected_base)
        assert tendency.amplitude == approx(expected_amplitude)
        assert tendency.min == approx(expected_min)
        assert tendency.max == approx(expected_max)


@pytest.mark.parametrize(
    "base, amplitude, min, max, expected_base, expected_amplitude, \
    expected_min, expected_max, has_error",
    [
        # Missing 2 value
        (None, None, 5, 15, 10, 5, 5, 15, False),
        (None, 5, None, 15, 10, 5, 5, 15, False),
        (None, 5, 5, None, 10, 5, 5, 15, False),
        (10, None, None, 15, 10, 5, 5, 15, False),
        (10, None, 5, None, 10, 5, 5, 15, False),
        (10, 5, None, None, 10, 5, 5, 15, False),
        # Missing 3 values
        (10, None, None, None, 10, 1, 9, 11, False),
        (None, 5, None, None, 8, 5, 3, 13, False),
        (None, None, 5, None, 8, 3, 5, 11, False),
        (None, None, None, 15, 8, 7, 1, 15, False),
        # Missing all values
        (None, None, None, None, 0, 1, -1, 1, False),
    ],
)
def test_bounds_next(
    base,
    amplitude,
    min,
    max,
    expected_base,
    expected_amplitude,
    expected_min,
    expected_max,
    has_error,
):
    """
    Test the base, amplitude, minimum and maximum values of the periodic base tendency,
    when the tendency has a next tendency.
    """
    next_tendency = ConstantTendency(duration=1, value=8)
    if has_error:
        with pytest.raises(ValueError):
            PeriodicBaseTendency(
                duration=1, base=base, amplitude=amplitude, min=min, max=max
            )
    else:
        tendency = PeriodicBaseTendency(
            duration=1, base=base, amplitude=amplitude, min=min, max=max
        )
        tendency.set_next_tendency(next_tendency)
        assert tendency.base == approx(expected_base)
        assert tendency.amplitude == approx(expected_amplitude)
        assert tendency.min == approx(expected_min)
        assert tendency.max == approx(expected_max)
