import csv

import click
import imas
import numpy as np
import pytest
from click.testing import CliRunner

from waveform_editor import cli as waveform_cli


@pytest.fixture
def test_yaml_file(tmp_path):
    """Creates a temporary YAML file with sample content."""
    yaml_content = """
    ec_launchers:
      beams:
        ec_launchers/beam(1)/phase/angle: 1
        ec_launchers/beam(2)/phase/angle: 2
        ec_launchers/beam(3)/phase/angle: 3
        ec_launchers/beam(4)/power_launched/data:
            - {to: 8.33e5, duration: 20}
            - {type: constant, duration: 20}
            - {duration: 25, to: 0}
    globals:
      dd_version: 4.0.0
    """
    yaml_file = tmp_path / "test_config.yaml"
    yaml_file.write_text(yaml_content)
    return yaml_file


@pytest.fixture
def test_csv_file(tmp_path):
    """Creates a temporary valid CSV file for time data."""
    csv_file = tmp_path / "times.csv"
    times = [0.1, 0.5, 1.0, 1.5, 2.0]
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(times)
    return csv_file, np.array(times)


@pytest.fixture
def test_invalid_csv_file_format(tmp_path):
    """Creates a temporary invalid CSV file (non-numeric)."""
    csv_file = tmp_path / "invalid_times_format.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([1, "a", 3])
    return csv_file


@pytest.fixture
def runner():
    """Provides a Click CliRunner instance."""
    return CliRunner()


@pytest.mark.parametrize(
    "invalid_input",
    [
        "1,2",  # Not enough parts
        "1,2,3,4",  # Too many parts
        "a,10,11",  # Non-numeric start
        "0,b,11",  # Non-numeric stop
        "0,10,c",  # Non-integer num
    ],
)
def test_parse_linspace_invalid(invalid_input):
    """Test parsing invalid linspace strings."""
    with pytest.raises(click.BadParameter):
        waveform_cli.parse_linspace(None, None, invalid_input)


def test_parse_linspace_none():
    """Test parsing None linspace string."""
    result = waveform_cli.parse_linspace(None, None, None)
    assert result is None
    result = waveform_cli.parse_linspace(None, None, "")
    assert result is None


def test_export_csv(runner, tmp_path, test_yaml_file, test_csv_file):
    csv_path, _ = test_csv_file
    output_csv = tmp_path / "test.csv"
    result = runner.invoke(
        waveform_cli.cli,
        [
            "export-csv",
            str(test_yaml_file),
            str(output_csv),
            "--csv",
            str(csv_path),
        ],
    )
    assert result.exit_code == 0
    assert output_csv.exists()


def test_export_csv_nested(runner, tmp_path, test_yaml_file, test_csv_file):
    csv_path, _ = test_csv_file
    output_csv = tmp_path / "subdir" / "subdir2" / "test.csv"
    result = runner.invoke(
        waveform_cli.cli,
        [
            "export-csv",
            str(test_yaml_file),
            str(output_csv),
            "--csv",
            str(csv_path),
        ],
    )
    assert result.exit_code == 0
    assert output_csv.exists()


def test_export_png(runner, tmp_path, test_yaml_file):
    result = runner.invoke(
        waveform_cli.cli,
        [
            "export-png",
            str(test_yaml_file),
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert tmp_path.exists()
    assert (tmp_path / "ec_launchers_beam(1)_phase_angle.png").exists()
    assert (tmp_path / "ec_launchers_beam(2)_phase_angle.png").exists()
    assert (tmp_path / "ec_launchers_beam(3)_phase_angle.png").exists()
    assert (tmp_path / "ec_launchers_beam(4)_power_launched_data.png").exists()


def test_export_png_nested(runner, tmp_path, test_yaml_file):
    full_path = tmp_path / "subdir" / "subdir2"
    result = runner.invoke(
        waveform_cli.cli,
        [
            "export-png",
            str(test_yaml_file),
            str(full_path),
        ],
    )
    assert result.exit_code == 0
    assert tmp_path.exists()
    assert (full_path / "ec_launchers_beam(1)_phase_angle.png").exists()
    assert (full_path / "ec_launchers_beam(2)_phase_angle.png").exists()
    assert (full_path / "ec_launchers_beam(3)_phase_angle.png").exists()
    assert (full_path / "ec_launchers_beam(4)_power_launched_data.png").exists()


def test_export_ids(runner, tmp_path, test_yaml_file):
    uri = tmp_path / "test.nc"
    result = runner.invoke(
        waveform_cli.cli,
        ["export-ids", str(test_yaml_file), str(uri), "--linspace", "0,3,5"],
    )
    assert result.exit_code == 0
    with imas.DBEntry(uri, "r", dd_version="4.0.0") as entry:
        ids = entry.get("ec_launchers")
        assert np.all(ids.beam[0].phase.angle == 1)
        assert np.all(ids.beam[1].phase.angle == 2)
        assert np.all(ids.beam[2].phase.angle == 3)
        assert len(ids.beam[3].power_launched.data) == 5


def test_export_ids_both(runner, tmp_path, test_yaml_file, test_csv_file):
    uri = tmp_path / "test.nc"
    csv_path, _ = test_csv_file
    result = runner.invoke(
        waveform_cli.cli,
        [
            "export-ids",
            str(test_yaml_file),
            str(uri),
            "--linspace",
            "0,3,5",
            "--csv",
            str(csv_path),
        ],
    )
    assert result.exit_code != 0


def test_export_ids_none(runner, tmp_path, test_yaml_file):
    uri = tmp_path / "test.nc"
    result = runner.invoke(
        waveform_cli.cli,
        ["export-ids", str(test_yaml_file), str(uri)],
    )
    assert result.exit_code != 0
