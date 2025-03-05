import csv
import logging
import sys

import click
import numpy as np
from rich import box, console, traceback
from rich.table import Table

import waveform_editor
from waveform_editor.waveform_exporter import WaveformExporter
from waveform_editor.yaml_parser import YamlParser

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


@cli.command("export-csv")
@click.argument("yaml", type=click.Path(exists=True))
@click.argument("output", type=str)
@click.option("--times", type=click.Path(exists=True))
@click.option("--num_interp", type=int)
def export_csv(yaml, output, times, num_interp):
    """Export waveform data to a CSV file."""
    exporter = setup_exporter(yaml, times, num_interp)
    exporter.to_csv(output)


@cli.command("export-png")
@click.argument("yaml", type=click.Path(exists=True))
@click.argument("output", type=str)
@click.option("--times", type=click.Path(exists=True))
@click.option("--num_interp", type=int)
def export_png(yaml, output, times, num_interp):
    """Export waveform data to a CSV file."""
    exporter = setup_exporter(yaml, times, num_interp)
    exporter.to_png(output)


@cli.command("export-ids")
@click.argument("yaml", type=str)
@click.argument("uri", type=str)
@click.option("--dd-version", type=str)
@click.option("--times", type=click.Path(exists=True))
@click.option("--num_interp", type=int)
def export_ids(yaml, uri, dd_version, times, num_interp):
    """Export waveform data to an IDS."""
    exporter = setup_exporter(yaml, times, num_interp)
    exporter.to_ids(uri, dd_version=dd_version)


def setup_exporter(yaml, times, num_interp):
    waveform = load_waveform_from_yaml(yaml)
    time_array = load_time_array(times, waveform, num_interp)
    exporter = WaveformExporter(waveform, times=time_array)
    return exporter


def load_time_array(times, waveform, num_interp):
    """Load time array from CSV file or use default linear interpolation."""
    if times:
        try:
            # assuming single column format
            with open(times, newline="") as csvfile:
                reader = csv.reader(csvfile)
                time_array = [float(row[0]) for row in reader if row]

            return np.array(time_array)
        except Exception as e:
            click.secho(
                f"Invalid time array file:\n {e}",
                fg="red",
            )
    start = waveform.get_start()
    end = waveform.get_end()
    if not num_interp:
        click.secho(
            "No time array provided, using linear interpolation with 1000 points.",
            fg="yellow",
        )
        num_interp = 1000
    return np.linspace(start, end, num_interp)


def load_waveform_from_yaml(yaml_file):
    with open(yaml_file) as file:
        yaml_str = file.read()
    yaml_parser = YamlParser()
    yaml_parser.parse_waveforms(yaml_str)
    annotations = yaml_parser.waveform.annotations
    if annotations:
        click.secho(
            "The following errors and warnings were detected in the YAML file:\n"
            f"{annotations}",
            fg="red",
        )
    return yaml_parser.waveform


if __name__ == "__main__":
    cli()
