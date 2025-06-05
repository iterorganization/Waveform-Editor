import csv

import numpy as np
import pytest

from waveform_editor.util import State, times_from_csv


def test_times_from_csv_valid(tmp_path):
    """Test loading a valid CSV time file."""

    csv_file = tmp_path / "times.csv"
    times = [0.1, 0.5, 1.0, 1.5, 2.0]
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(times)
    result = times_from_csv(csv_file)
    np.testing.assert_array_equal(result, np.array(times))


def test_times_from_csv_nonexistent(tmp_path):
    """Test loading a non-existent CSV file."""
    non_existent_path = tmp_path / "not_a_file.csv"
    with pytest.raises(FileNotFoundError):
        times_from_csv(non_existent_path)


def test_times_from_csv_invalid_rows(tmp_path):
    """Test loading a CSV file with incorrect number of rows."""

    csv_file = tmp_path / "invalid_times_rows.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([1, 2, 3])
        writer.writerow([4, 5, 6])
    with pytest.raises(ValueError):
        times_from_csv(csv_file)


def test_times_from_csv_invalid_format(tmp_path):
    """Test loading a CSV file with non-numeric values."""

    csv_file = tmp_path / "invalid_times_format.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([1, "a", 3])
    with pytest.raises(ValueError):
        times_from_csv(csv_file)


def test_times_from_csv_none():
    """Test calling times_from_csv with None."""
    assert times_from_csv(None) is None


def test_state():
    state = State()

    assert bool(state) is False
    with state:
        assert bool(state) is True
    assert bool(state) is False

    # Test that state returns to False on exceptions
    try:
        with state:
            assert bool(state) is True
            1 / 0  # noqa
    except ZeroDivisionError:
        pass
    assert bool(state) is False

    # enter state twice is an error:
    with pytest.raises(RuntimeError), state, state:
        pass
