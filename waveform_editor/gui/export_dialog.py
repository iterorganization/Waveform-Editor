import logging
from pathlib import Path

import numpy as np
import panel as pn

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


class ExportDialog:
    """Handles the UI and logic for exporting waveform configurations."""

    def __init__(self, main_gui):
        """
        Initialize the Export Dialog.

        Args:
            main_gui: A reference to the main WaveformEditorGui instance.
        """
        self.main_gui = main_gui
        self.progress = pn.indicators.Progress(
            name="Progress", value=0, visible=False, margin=(15, 5)
        )

        # Output Type
        export_formats = [IDS_EXPORT, CSV_EXPORT, PNG_EXPORT]
        self.export_format = pn.widgets.RadioBoxGroup(
            name="Export Format",
            options=export_formats,
            value=export_formats[0],
            inline=True,
        )
        self.time_source = pn.widgets.RadioBoxGroup(
            name="Time Basis",
            options=[LINSPACE, CSVFILE, MANUALINPUT],
            value=LINSPACE,
            inline=True,
        )
        self.input = pn.widgets.TextInput()
        output_option_box = pn.WidgetBox(
            pn.pane.Markdown("### 📤 Output type"),
            self.export_format,
            self.input,
            sizing_mode="stretch_width",
            margin=(10, 5),
        )
        self.error_alert = pn.pane.Alert(alert_type="danger", visible=False)

        # Time Options
        self.time_manual_input = pn.widgets.TextInput(
            name="Time Input", placeholder="e.g. 1,2,3,4,5"
        )
        self.csv_file_input = pn.widgets.FileInput(
            name="Time CSV File", accept=".csv", visible=False
        )
        self.linspace_start = pn.widgets.FloatInput(name="Start", value=0.0, width=100)
        self.linspace_stop = pn.widgets.FloatInput(name="Stop", value=1.0, width=100)
        self.linspace_num = pn.widgets.IntInput(
            name="Num Points", value=101, step=1, start=2, width=100
        )
        self.linspace_row = pn.Row(
            self.linspace_start, self.linspace_stop, self.linspace_num
        )
        time_options_box = pn.WidgetBox(
            pn.pane.Markdown("### ⏱️ Time Options"),
            self.time_source,
            self.linspace_row,
            self.csv_file_input,
            self.time_manual_input,
            sizing_mode="stretch_width",
            margin=(10, 5),
        )

        self.export_button = pn.widgets.Button(
            name="Export", button_type="primary", disabled=True
        )
        cancel_button = pn.widgets.Button(name="Cancel")

        layout = pn.Column(
            pn.pane.Markdown("## Export Configuration"),
            output_option_box,
            time_options_box,
            self.error_alert,
            pn.Row(self.export_button, cancel_button, self.progress),
            sizing_mode="stretch_width",
        )
        self.modal = pn.Modal(layout)

        # Callbacks
        self.input.param.watch(self._validate_export_ready, "value_input")
        self.time_manual_input.param.watch(self._validate_export_ready, "value_input")
        self.csv_file_input.param.watch(self._validate_export_ready, "value")
        self.time_source.param.watch(self._validate_export_ready, "value")
        self.export_format.param.watch(self._validate_export_ready, "value")
        self.export_format.param.watch(self._update_ui, "value")
        self.time_source.param.watch(self._update_ui, "value")
        self.export_button.on_click(self._handle_export)
        cancel_button.on_click(self._close)

    def _update_ui(self, event=None):
        """Update visibility of widgets based on selections."""

        placeholders = {
            "IDS": "e.g. imas:hdf5?path=testdb",
            "PNG": "e.g. /path/to/export/pngs",
            "CSV": "e.g. /path/to/export/output.csv",
        }
        self.input.placeholder = placeholders[self.export_format.value]
        value = self.time_source.value
        options = self.time_source.options
        self.linspace_row.visible = value == LINSPACE
        self.csv_file_input.visible = value == CSVFILE
        self.time_manual_input.visible = value == MANUALINPUT

        # Add Default option to PNG export
        if self.export_format.value == PNG_EXPORT:
            if DEFAULT not in options:
                options.append(DEFAULT)
        else:
            if DEFAULT in options:
                options.remove(DEFAULT)
                if self.time_source.value == DEFAULT:
                    self.time_source.value = self.time_source.options[0]

        self.time_source.param.trigger("options")

    def _get_times(self):
        """Parse inputs and return the time array."""
        if self.time_source.value == LINSPACE:
            return np.linspace(
                self.linspace_start.value,
                self.linspace_stop.value,
                self.linspace_num.value,
            )
        elif self.time_source.value == CSVFILE:
            if not self.csv_file_input.value:
                raise ValueError("Please select a CSV file for the time basis.")
            try:
                return times_from_csv(self.csv_file_input.value, from_file_path=False)
            except Exception as e:
                raise ValueError(f"Invalid time CSV file.\n{e}") from e
        elif self.time_source.value == MANUALINPUT:
            return self.time_array

    def _handle_export(self, event):
        """Perform the export based on current settings."""
        self.error_alert.visible = False
        self.progress.visible = True
        input = self.input.value_input
        try:
            times = self._get_times() if self.time_source.value != DEFAULT else None
            exporter = ConfigurationExporter(
                self.main_gui.config, times, progress=self.progress
            )
            export_type = self.export_format.value
            if not input:
                pn.state.notifications.error("Please provide an output location.")
                return

            if export_type == IDS_EXPORT:
                exporter.to_ids(input)
            elif export_type == PNG_EXPORT:
                exporter.to_png(Path(input))
            elif export_type == CSV_EXPORT:
                exporter.to_csv(Path(input))
            self.progress.value = 100
            pn.state.notifications.success("Succesfully exported configuration")
            self._close()
        except Exception as e:
            self.error_alert.visible = True
            self.error_alert.object = f"### Export failed!\n{e}"

        self.progress.value = 0
        self.progress.visible = False

    def _validate_export_ready(self, *events):
        """Enable or disable export button based on input validation."""
        valid = bool(self.input.value_input.strip())

        if self.time_source.value == CSVFILE:
            valid &= bool(self.csv_file_input.value)
        elif self.time_source.value == MANUALINPUT:
            try:
                self.time_array = np.fromstring(
                    self.time_manual_input.value_input, sep=","
                )
                valid &= self.time_array.size > 0
            except Exception:
                valid = False

        self.export_button.disabled = not valid

    def open(self, event):
        """Open the export modal dialog."""
        self._update_ui()
        self.modal.show()

    def _close(self, event=None):
        """Close the export modal dialog."""
        self.modal.hide()

    def __panel__(self):
        return self.modal
