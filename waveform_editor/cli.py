import logging
import sys
from pathlib import Path

import click
import numpy as np
from rich import console, traceback

import waveform_editor
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.exporter import ConfigurationExporter
from waveform_editor.util import times_from_csv

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
    click.echo(f"Waveform editor version: {waveform_editor.__version__}")


def parse_linspace(ctx, param, value):
    """Parse linspace string into a tuple."""
    if not value:
        return None
    try:
        start_str, stop_str, num_str = value.split(",")
        return float(start_str), float(stop_str), int(num_str)
    except Exception as e:
        raise click.BadParameter(
            "Must be in the format: start,stop,num (e.g. 0,5,6)"
        ) from e


@cli.command("gui")
def launch_gui():
    """Launch the Waveform Editor GUI using Panel."""
    # Use local imports to avoid loading the full GUI dependencies for the other CLI use
    # cases:
    import panel as pn

    from waveform_editor.gui.main import WaveformEditorGui

    try:
        app = WaveformEditorGui()
        pn.serve(app)
    except Exception as e:
        logger.error(f"Failed to launch GUI: {e}")


@cli.command("export-ids")
@click.argument("yaml", type=click.Path(exists=True))
@click.argument("uri", type=str)
@click.option("--csv", type=click.Path(exists=False))
@click.option("--linspace", callback=parse_linspace)
def export_ids(yaml, uri, csv, linspace):
    """Export waveform data to an IDS.

    \b
    Arguments:
      yaml: Path to the waveform YAML file.
      uri: URI of the output Data Entry.
    \b
    Options:
      csv: CSV file containing a custom time array.
      linspace: linspace containing start, stop and num values, e.g. 0,3,4

    Note: The csv containing the time values should be formatted as a single row,
    delimited by commas, For example: `1,2,3,4,5`.
    """
    if not csv and not linspace:
        raise click.UsageError("Either --csv or --linspace must be provided")
    exporter = create_exporter(yaml, csv, linspace)
    exporter.to_ids(uri)


@cli.command("export-png")
@click.argument("yaml", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path(exists=False))
@click.option("--csv", type=click.Path(exists=False))
@click.option("--linspace", callback=parse_linspace)
def export_png(yaml, output_dir, csv, linspace):
    """Export waveform data to a PNG file.
    \b
    Arguments:
      yaml: Path to the waveform YAML file.
      output_dir: Path to output directory where the PNG files will be saved.
    \b
    Options:
      csv: CSV file containing a custom time array.
      linspace: linspace containing start, stop and num values, e.g. 0,3,4

    Note: The csv containing the time values should be formatted as a single row,
    delimited by commas, For example: `1,2,3,4,5`.
    """
    exporter = create_exporter(yaml, csv, linspace)
    output_path = Path(output_dir)
    exporter.to_png(output_path)


@cli.command("export-csv")
@click.argument("yaml", type=click.Path(exists=True))
@click.argument("output_csv", type=click.Path(exists=False))
@click.option("--csv", type=click.Path(exists=False))
@click.option("--linspace", callback=parse_linspace)
def export_csv(yaml, output_csv, csv, linspace):
    """Export waveform data to a CSV file.
    \b
    Arguments:
      yaml: Path to the waveform YAML file.
      output_csv: Path to output CSV file.
    \b
    Options:
      csv: CSV file containing a custom time array.
      linspace: linspace containing start, stop and num values, e.g. 0,3,4

    Note: The csv containing the time values should be formatted as a single row,
    delimited by commas, For example: `1,2,3,4,5`.
    """
    if not csv and not linspace:
        raise click.UsageError("Either --csv or --linspace must be provided")
    exporter = create_exporter(yaml, csv, linspace)
    output_path = Path(output_csv)
    exporter.to_csv(output_path)


@cli.command("actor")
def actor():
    """Run the MUSCLE3 actor.

    This command does not accept any options or arguments: configuration of the actor is
    done through MUSCLE3 settings. Please have a look at the documentation for more
    details: https://waveform-editor.readthedocs.io/
    """
    try:
        import libmuscle  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "The muscle3 python package is required to run the waveform-editor actor."
        ) from exc
    from waveform_editor.muscle3 import waveform_actor

    waveform_actor()


def create_exporter(yaml, csv, linspace):
    """Read a YAML file from disk, load it into a WaveformConfiguration and create a
    ConfigurationExporter using the given times.

    Args:
        yaml: The YAML file to load into a configuration.
        csv: CSV file containing time values.
        linspace: Tuple containing the start, stop and number of the linspace.

    Returns:
        The ConfigurationExporter of the loaded YAML file.
    """
    if csv and linspace:
        raise click.UsageError("Cannot provide both --csv and --linspace.")
    elif csv:
        times = times_from_csv(csv)
    elif linspace:
        start = linspace[0]
        stop = linspace[1]
        num = linspace[2]
        times = np.linspace(start, stop, num)
    else:
        times = None

    config = WaveformConfiguration()
    load_config(config, Path(yaml))
    exporter = ConfigurationExporter(config, times)
    return exporter


def load_config(config: WaveformConfiguration, filepath: Path) -> None:
    """Load the YAML file from disk with the provided configuration.

    Args:
        config: configuration to load the file with
        filepath: Path to the yaml file
    """
    if not filepath.is_file():
        raise ValueError(f"Cannot find waveform configuration file '{filepath}'")
    logging.debug("Loading waveform configuration from %s", filepath)

    config.clear()
    config.parser.load_yaml(filepath)

    if config.load_error:  # Set when the YAML could not be parsed
        raise RuntimeError(f"Could not load waveforms: {config.load_error}")

    # Warn for any waveform with issues
    for name, group in config.waveform_map.items():
        waveform = group[name]
        if waveform.annotations:
            details = "\n".join(
                "- " + item["text"].replace("\n", "\n  ").strip()
                for item in waveform.annotations
            )
            logger.warning("Found issues with waveform '%s':\n%s", name, details)


if __name__ == "__main__":
    cli()
