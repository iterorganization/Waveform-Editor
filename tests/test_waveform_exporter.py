import csv
from pathlib import Path

import imas
import numpy as np
import pytest

from waveform_editor.waveform import Waveform
from waveform_editor.waveform_exporter import WaveformExporter


@pytest.fixture
def waveform_list():
    return [
        {
            "user_type": "linear",
            "user_from": 0,
            "user_to": 8,
            "user_duration": 5,
            "line_number": 1,
        },
        {
            "user_type": "sine-wave",
            "user_base": 8,
            "user_amplitude": 2,
            "user_frequency": 1,
            "user_duration": 4,
            "line_number": 2,
        },
        {
            "user_type": "constant",
            "user_value": 8,
            "user_duration": 3,
            "line_number": 3,
        },
        {
            "user_type": "smooth",
            "user_from": 8,
            "user_to": 0,
            "user_duration": 2,
            "line_number": 4,
        },
    ]


@pytest.fixture
def waveform(waveform_list):
    return Waveform(waveform=waveform_list)


@pytest.fixture
def times():
    return np.array([0, 1, 2, 3, 4, 5])


@pytest.fixture
def exporter(waveform, times):
    return WaveformExporter(waveform, times=times)


def test_parse_uri(exporter):
    """Test if URIs are parsed correctly."""
    uri = "imas:hdf5?path=./testdb#ec_launchers/beam(1)/power_launched"
    parsed_uri = exporter.parse_uri(uri)
    assert parsed_uri == (
        "imas:hdf5?path=./testdb",
        "ec_launchers",
        0,
        "/beam(1)/power_launched",
    )
    uri2 = "imas:hdf5?path=./testdb/test_loc#ec_launchers:1/beam(1)/power_launched"
    parsed_uri = exporter.parse_uri(uri2)
    assert parsed_uri == (
        "imas:hdf5?path=./testdb/test_loc",
        "ec_launchers",
        1,
        "/beam(1)/power_launched",
    )

    uri3 = "imas:hdf5?path=./test_db#equilibrium/time_slice()/boundary/elongation"
    parsed_uri = exporter.parse_uri(uri3)
    assert parsed_uri == (
        "imas:hdf5?path=./test_db",
        "equilibrium",
        0,
        "/time_slice()/boundary/elongation",
    )

    uri4 = "test_db.nc#equilibrium/time_slice()/boundary/elongation"
    parsed_uri = exporter.parse_uri(uri4)
    assert parsed_uri == (
        "test_db.nc",
        "equilibrium",
        0,
        "/time_slice()/boundary/elongation",
    )


def test_to_csv(exporter, tmp_path):
    """Test if exported CSV exists and is filled with correct times and values."""
    file_path = tmp_path / "waveform.csv"
    exporter.to_csv(file_path)

    with open(file_path, newline="") as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)

    assert Path(file_path).exists()
    assert len(rows) == len(exporter.times) + 1  # Header + data rows
    for i, (time, value) in enumerate(zip(exporter.times, exporter.values), start=1):
        assert float(rows[i][0]) == time
        assert float(rows[i][1]) == value


def test_to_png(exporter, tmp_path):
    """Test if exported PNG exists."""
    file_path = tmp_path / "waveform.png"
    exporter.to_png(file_path)
    assert Path(file_path).exists()


def test_to_ids_flt1d(exporter, tmp_path):
    """Check if FLT_1D is filled correctly for a homogeneous time IDS."""
    file_path = f"{tmp_path}/test_ec_launchers.nc"

    uri = f"{file_path}#ec_launchers/beam(1)/power_launched"
    exporter.to_ids(uri)

    with imas.DBEntry(file_path, "r") as dbentry:
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.time == exporter.times)
        assert np.all(ids.beam[0].power_launched.data == exporter.values)


def test_to_ids_flt1d_heterogeneous(exporter, tmp_path):
    """Check if FLT_1D is filled correctly for a heterogeneous time IDS."""
    file_path = f"{tmp_path}/test_ec_launchers.nc"

    uri = f"{file_path}#ec_launchers/beam(1)/power_launched"
    exporter.to_ids(uri, is_homogeneous=False)

    with imas.DBEntry(file_path, "r") as dbentry:
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(ids.beam[0].power_launched.time == exporter.times)
        assert np.all(ids.beam[0].power_launched.data == exporter.values)


def test_to_ids_flt1d_occurrence(exporter, tmp_path):
    """Check if FLT_1D is filled correctly when providing an occurrence number."""
    file_path = f"{tmp_path}/test_ec_launchers.nc"

    uri = f"{file_path}#ec_launchers:1/beam(1)/power_launched"
    exporter.to_ids(uri)

    with imas.DBEntry(file_path, "r") as dbentry:
        # Check if only occurrence 1 is filled
        with pytest.raises(IndexError):
            ids = dbentry.get("ec_launchers", occurrence=0, autoconvert=False)

        ids = dbentry.get("ec_launchers", occurrence=1, autoconvert=False)
        assert np.all(ids.time == exporter.times)
        assert np.all(ids.beam[0].power_launched.data == exporter.values)


def test_to_ids_flt0d(exporter, tmp_path):
    """Check if FLT_0D is filled correctly for a homogeneous time IDS."""
    file_path = f"{tmp_path}/test_equilibrium.nc"

    uri = f"{file_path}#equilibrium/time_slice()/boundary/elongation"
    exporter.to_ids(uri)

    with imas.DBEntry(file_path, "r") as dbentry:
        ids = dbentry.get("equilibrium", autoconvert=False)
        assert np.all(ids.time == exporter.times)
        for i, time_slice in enumerate(ids.time_slice):
            assert time_slice.boundary.elongation == exporter.values[i]


def test_to_ids_flt0d_heterogeneous(exporter, tmp_path):
    """Check if FLT_0D is filled correctly for a heterogeneous time IDS."""
    file_path = f"{tmp_path}/test_equilibrium.nc"

    uri = f"{file_path}#equilibrium/time_slice()/boundary/elongation"
    exporter.to_ids(uri, is_homogeneous=False)

    with imas.DBEntry(file_path, "r") as dbentry:
        ids = dbentry.get("equilibrium", autoconvert=False)
        imas.util.print_tree(ids)
        for i, time_slice in enumerate(ids.time_slice):
            assert time_slice.boundary.elongation == exporter.values[i]
            assert time_slice.time == exporter.times[i]


def test_to_ids_no_times(tmp_path):
    """Check if FLT_1D is filled correctly when not providing a time array."""
    waveform_list = [
        {
            "user_type": "linear",
            "user_from": 0,
            "user_to": 8,
            "user_start": 5,
            "user_duration": 5,
            "line_number": 1,
        }
    ]
    waveform = Waveform(waveform=waveform_list)
    exporter = WaveformExporter(waveform)

    file_path = f"{tmp_path}/test_ec_launchers.nc"

    uri = f"{file_path}#ec_launchers/beam(1)/power_launched"
    exporter.to_ids(uri)

    with imas.DBEntry(file_path, "r") as dbentry:
        ids = dbentry.get("ec_launchers", autoconvert=False)
        assert np.all(np.isclose(ids.time, [5, 10]))
        assert np.all(np.isclose(ids.beam[0].power_launched.data, [0, 8]))
