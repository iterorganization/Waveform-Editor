import csv
import logging
import sys
from pathlib import Path

import click
import numpy as np
from rich import box, console, traceback
from rich.table import Table

import waveform_editor
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.exporter import ConfigurationExporter

logger = logging.getLogger(__name__)


def _excepthook(type_, value, tb):
    logger.debug("Suppressed traceback:", exc_info=(type_, value, tb))
    # Only display the last traceback frame:
    if tb is not None:
        while tb.tb_next:
            tb = tb.tb_next
    rich_tb = traceback.Traceback.from_exception(type_, value, tb, extra_lines=0)
    console.Console(stderr=True).print(rich_tb)


@click.group("waveform-editor", invoke_without_command=True, no_args_is_help=True)
@click.option("-v", "--version", is_flag=True, help="Show version information")
def cli(version):
    """The Waveform Editor command line interface.

    Please use one of the available commands listed below. You can get help for each
    command by executing:

        waveform-editor <command> --help
    """
    # Limit the traceback to 1 item: avoid scaring CLI users with long traceback prints
    # and let them focus on the actual error message
    sys.excepthook = _excepthook

    if version:
        print_version()


def print_version():
    """Print version information of the waveform editor."""
    cons = console.Console()
    grid = Table(
        title="waveform editor version info", show_header=False, title_style="bold"
    )
    grid.box = box.HORIZONTALS
    if cons.size.width > 120:
        grid.width = 120
    grid.add_row("waveform editor version:", waveform_editor.__version__)
    grid.add_section()
    console.Console().print(grid)


@cli.command("export-ids")
@click.argument("yaml", type=str)
@click.argument("uri", type=str)
@click.argument("times", type=click.Path(exists=True))
def export_ids(yaml, uri, times):
    """Export waveform data to an IDS.

    \b
    Arguments:
      yaml: Path to the waveform YAML file.
      uri: URI of the output Data Entry.
      times: CSV file containing a custom time array.

    Note: The csv containing the time values should be formatted as a single row,
    delimited by commas, For example: `1,2,3,4,5`.
    """
    config = load_config(yaml)
    times = load_times_file(times)
    exporter = ConfigurationExporter(config, times)
    exporter.to_ids(uri)


@cli.command("export-png")
@click.argument("yaml", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path(exists=False))
@click.option("--times", type=click.Path(exists=True))
def export_png(yaml, output_dir, times):
    """Export waveform data to a PNG file.
    \b
    Arguments:
      yaml: Path to the waveform YAML file.
      output_dir: Path to output directory where the PNG files will be saved.
    \b
    Options:
      --times: CSV file containing a custom time array.

    Note: The csv containing the time values should be formatted as a single row,
    delimited by commas, For example: `1,2,3,4,5`.
    """
    if times is not None:
        times = load_times_file(times)
    config = load_config(yaml)
    exporter = ConfigurationExporter(config, times)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    exporter.to_png(output_path)


@cli.command("export-csv")
@click.argument("yaml", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path(exists=False))
@click.argument("times", type=click.Path(exists=True))
def export_csv(yaml, output_dir, times):
    """Export waveform data to a CSV file.
    \b
    Arguments:
      yaml: Path to the waveform YAML file.
      uri: URI of the output Data Entry.
      times: CSV file containing a custom time array.

    Note: The csv containing the time values should be formatted as a single row,
    delimited by commas, For example: `1,2,3,4,5`.
    """
    config = load_config(yaml)
    times = load_times_file(times)
    exporter = ConfigurationExporter(config, times)
    output_path = Path(output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    exporter.to_csv(output_path)


def load_config(yaml):
    with open(yaml) as file:
        yaml_str = file.read()

    config = WaveformConfiguration()
    config.parser.load_yaml(yaml_str)
    return config


def load_times_file(times_file):
    try:
        with open(times_file, newline="") as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

            if len(rows) != 1:
                raise ValueError(
                    "File must contain exactly one row of comma-separated values."
                )

            # Parse the single row into floats
            time_array = [float(value) for value in rows[0]]

        return np.array(time_array)

    except Exception as e:
        raise click.ClickException(
            "Invalid time array file. Ensure the times CSV contains a single row of "
            f"comma-separated values.\nFor example: 1,2,3,4\n\nDetails: {e}"
        ) from e


if __name__ == "__main__":
    cli()
