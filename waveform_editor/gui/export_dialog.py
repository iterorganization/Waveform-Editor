import logging
from pathlib import Path

import numpy as np
import panel as pn
import param

from waveform_editor.exporter import ConfigurationExporter
from waveform_editor.util import times_from_csv

logger = logging.getLogger(__name__)


LINSPACE = "Linspace"
CSVFILE = "CSV File"
MANUALINPUT = "Manual"
IDS_EXPORT = "IDS"
CSV_EXPORT = "CSV"
PNG_EXPORT = "PNG"
DEFAULT = "Default"

TIME_MODES = [LINSPACE, CSVFILE, MANUALINPUT]
TIME_MODES_FOR_PNG = [DEFAULT, *TIME_MODES]


class ExportDialog(param.Parameterized):
    """Handles the UI and logic for exporting waveform configurations."""

    # Export type selection
    export_type = param.Selector(objects=[IDS_EXPORT, CSV_EXPORT, PNG_EXPORT])
    # IMAS URI or output path
    output = param.String()

    # Time parameters
    time_mode = param.Selector(objects=TIME_MODES)
    linspace_start = param.Number(default=0.0)
    linspace_stop = param.Number(default=1.0)
    linspace_num = param.Integer(default=101)
    csvfile = param.Bytes()
    time_array_input = param.String()

    # Error placeholder
    error_alert = param.String()
    export_disabled_description = param.String()

    def __init__(self, main_gui):
        """
        Initialize the Export Dialog.

        Args:
            main_gui: A reference to the main WaveformEditorGui instance.
        """
        super().__init__()
        self.main_gui = main_gui
        self.time_array = None  # set when time_array_input is updated

        # Export type options
        output_option_box = pn.WidgetBox(
            pn.pane.Markdown("### 📤 Output type"),
            pn.widgets.RadioBoxGroup.from_param(self.param.export_type, inline=True),
            pn.widgets.TextInput.from_param(
                self.param.output,
                name=self._export_type_description,
                placeholder=self._export_type_placeholder,
                onkeyup=True,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
            margin=(10, 5),
        )

        # Time Options
        time_options_box = pn.WidgetBox(
            pn.pane.Markdown("### ⏱️ Time Options"),
            pn.widgets.RadioBoxGroup.from_param(self.param.time_mode, inline=True),
            pn.pane.HTML(self._time_mode_description, styles={"font-style": "italic"}),
            self._time_mode_ui_element,
            sizing_mode="stretch_width",
            margin=(10, 5),
        )

        # Progress bar, error description and Export / Cancel buttons
        self.progress = pn.indicators.Progress(
            name="Progress", value=0, visible=False, margin=(15, 5)
        )
        export_button = pn.widgets.Button(
            name="Export",
            button_type="primary",
            disabled=self.param.export_disabled_description.rx.pipe(bool),
            on_click=self._handle_export,
        )
        cancel_button = pn.widgets.Button(name="Cancel", on_click=self._close)

        # Main layout
        layout = pn.Column(
            pn.pane.Markdown("## Export waveforms"),
            output_option_box,
            time_options_box,
            pn.pane.Alert(
                self.param.export_disabled_description,
                visible=self.param.export_disabled_description.rx.pipe(bool),
            ),
            pn.pane.Alert(
                self.param.error_alert,
                visible=self.param.error_alert.rx.pipe(bool),
                alert_type="danger",
            ),
            pn.Row(export_button, cancel_button),
            self.progress,
            sizing_mode="stretch_width",
        )
        self.modal = pn.Modal(layout, width=500)

        # Check if export button should be disabled
        self._export_disabled()

    @param.depends("export_type")
    def _export_type_placeholder(self):
        """Output path placeholder, based on the selected export type."""
        return {
            IDS_EXPORT: "e.g. imas:hdf5?path=testdb",
            PNG_EXPORT: "e.g. /path/to/export/pngs",
            CSV_EXPORT: "e.g. /path/to/export/output.csv",
        }[self.export_type]

    @param.depends("export_type")
    def _export_type_description(self):
        """Help description for the selected export type."""
        return {
            IDS_EXPORT: "Please enter the output IMAS URI below:",
            PNG_EXPORT: "Please enter an output folder below:",
            CSV_EXPORT: "Please enter an output file below:",
        }[self.export_type]

    @param.depends("export_type", watch=True)
    def _update_time_mode(self):
        """Add DEFAULT time mode when selecting PNG export."""
        if self.export_type == PNG_EXPORT:
            self.param["time_mode"].objects = TIME_MODES_FOR_PNG
            self.time_mode = DEFAULT
        else:
            if self.time_mode == DEFAULT:
                self.time_mode = LINSPACE
            self.param["time_mode"].objects = TIME_MODES
        self.param.trigger("time_mode")

    @param.depends("time_mode")
    def _time_mode_ui_element(self):
        """Create the time selection UI element(s) for the selected time mode."""
        return {
            LINSPACE: pn.Row(
                pn.widgets.FloatInput.from_param(
                    self.param.linspace_start, name="Start", width=100
                ),
                pn.widgets.FloatInput.from_param(
                    self.param.linspace_stop, name="Stop", width=100
                ),
                pn.widgets.NumberInput.from_param(
                    self.param.linspace_num, name="Num points", width=100
                ),
            ),
            CSVFILE: pn.widgets.FileInput.from_param(self.param.csvfile),
            MANUALINPUT: pn.widgets.TextInput.from_param(
                self.param.time_array_input, placeholder="e.g. 1,2,3,4,5", onkeyup=True
            ),
        }.get(self.time_mode, None)  # DEFAULT has no time mode UI element

    @param.depends("time_mode")
    def _time_mode_description(self):
        """Description of the selected time mode."""
        return {
            LINSPACE: "Linearly spaced time array. Start and Stop are both included.",
            CSVFILE: (
                "Upload a CSV file with time points. The file should contain a "
                "single line, with values separated by commas."
            ),
            MANUALINPUT: "Explicitly provide the time array below.",
            DEFAULT: "Automatically determine the time array for each waveform.",
        }[self.time_mode]

    @param.depends("time_mode", "output", "csvfile", "time_array_input", watch=True)
    def _export_disabled(self):
        """Determine if the export button is enabled or disabled."""
        message = ""
        if not self.output:
            message = "Missing output URI/path"
        elif self.time_mode == CSVFILE and not bool(self.csvfile):
            message = "No or empty CSV file uploaded"
        elif self.time_mode == MANUALINPUT:
            input = self.time_array_input
            try:
                self.time_array = np.array(
                    [float(x) for x in input.split(",") if x.strip()]
                )
                if not self.time_array.size:
                    message = "No or empty time array provided"
            except Exception as e:
                message = f"Invalid input for time array: {e}"
        self.export_disabled_description = message

    def _get_times(self):
        """Parse inputs and return the time array."""
        if self.time_mode == LINSPACE:
            return np.linspace(
                self.linspace_start, self.linspace_stop, self.linspace_num
            )
        elif self.time_mode == CSVFILE:
            if not self.csvfile:
                raise ValueError("Please select a CSV file for the time basis.")
            try:
                return times_from_csv(self.csvfile, from_file_path=False)
            except Exception as e:
                raise ValueError(f"Invalid time CSV file.\n{e}") from e
        elif self.time_mode == MANUALINPUT:
            return self.time_array

    def _handle_export(self, event):
        """Perform the export based on current settings."""
        self.error_alert = ""
        self.progress.visible = True
        try:
            times = self._get_times() if self.time_mode != DEFAULT else None
            exporter = ConfigurationExporter(self.main_gui.config, times, self.progress)

            if self.export_type == IDS_EXPORT:
                exporter.to_ids(self.output)
            elif self.export_type == PNG_EXPORT:
                exporter.to_png(Path(self.output))
            elif self.export_type == CSV_EXPORT:
                exporter.to_csv(Path(self.output))
            self.progress.value = 100
            pn.state.notifications.success("Succesfully exported configuration")
            self._close()
        except Exception as e:
            logger.error("Error during export", exc_info=1)
            self.error_alert = f"### Export failed!\n{e}"

        self.progress.value = 0
        self.progress.visible = False

    def open(self, event):
        """Open the export modal dialog."""
        self.modal.show()

    def _close(self, event=None):
        """Close the export modal dialog."""
        self.modal.hide()

    def __panel__(self):
        return self.modal
