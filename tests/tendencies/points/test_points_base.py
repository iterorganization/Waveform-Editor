from unittest.mock import patch

import numpy as np
import pytest

from waveform_editor.tendencies.points.points_base import PointsBaseTendency


@pytest.fixture(autouse=True)
def patch_points_base_tendency():
    arr = np.array([0.0])
    with (
        patch.object(PointsBaseTendency, "get_value", return_value=(arr, arr)),
        patch.object(PointsBaseTendency, "get_derivative", return_value=arr),
    ):
        yield


def test_empty():
    """Test empty tendency."""
    tendency = PointsBaseTendency()
    assert tendency.annotations

    tendency = PointsBaseTendency(user_time=[1, 2, 3])
    assert tendency.annotations

    tendency = PointsBaseTendency(user_value=[1, 2, 3])
    assert tendency.annotations


def test_filled():
    """Test value of filled tendency."""
    tendency = PointsBaseTendency(user_time=[1, 2, 3], user_value=[2, 4, 6])
    assert np.all(tendency.time == np.array([1, 2, 3]))
    assert np.all(tendency.value == np.array([2, 4, 6]))
    assert tendency.value_type is float
    assert tendency.start == 1
    assert tendency.end == 3
    assert not tendency.annotations


def test_filled_invalid():
    """Test value of filled tendency with invalid parameters."""
    # Not monotonically increasing
    tendency = PointsBaseTendency(
        user_time=np.array([3, 2, 1]), user_value=np.array([1, 2, 3])
    )
    assert tendency.annotations

    # Mismatched lengths
    tendency = PointsBaseTendency(
        user_time=np.array([1, 2]), user_value=np.array([1, 2, 3])
    )
    assert tendency.annotations

    # Not strictly increasing (repeated time point)
    tendency = PointsBaseTendency(
        user_time=np.array([1, 1, 2]), user_value=np.array([1, 2, 3])
    )
    assert tendency.annotations

    # Empty arrays
    tendency = PointsBaseTendency(user_time=[], user_value=[])
    assert tendency.annotations

    # Non-finite value
    tendency = PointsBaseTendency(user_time=[1, 2, 3], user_value=[1, float("inf"), 3])
    assert tendency.annotations


def test_start_duration_end_not_allowed():
    """Test that `start`, `duration`, and `end` may not be provided; they are always
    derived from `time[0]`/`time[-1]`."""
    tendency = PointsBaseTendency(
        user_time=[1, 2, 3], user_value=[1, 2, 3], user_start=1
    )
    assert tendency.annotations

    tendency = PointsBaseTendency(
        user_time=[1, 2, 3], user_value=[1, 2, 3], user_duration=2
    )
    assert tendency.annotations

    tendency = PointsBaseTendency(user_time=[1, 2, 3], user_value=[1, 2, 3], user_end=3)
    assert tendency.annotations

    tendency = PointsBaseTendency(
        user_time=[1, 2, 3],
        user_value=[1, 2, 3],
        user_start=1,
        user_duration=2,
        user_end=3,
    )
    assert tendency.annotations


def test_single_point():
    """Test that a single time/value point is allowed (a zero-duration tendency)."""
    tendency = PointsBaseTendency(user_time=[1.1], user_value=[9.9])
    assert tendency.time == np.array([1.1])
    assert tendency.value == np.array([9.9])
    assert tendency.start == 1.1
    assert tendency.end == 1.1
    assert not tendency.annotations
