import logging
import sys

import click
from rich import box, console, traceback
from rich.table import Table

import waveform_editor

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


if __name__ == "__main__":
    cli()
