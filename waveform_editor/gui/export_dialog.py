import logging
from pathlib import Path

import numpy as np
import panel as pn

from waveform_editor.exporter import ConfigurationExporter
from waveform_editor.util import times_from_csv

logger = logging.getLogger(__name__)


class ExportDialog:
    """Handles the UI and logic for exporting waveform configurations."""

    def __init__(self, main_gui):
        """
        Initialize the Export Dialog.

        Args:
            main_gui: A reference to the main WaveformEditorGui instance.
        """
        self.main_gui = main_gui

        # Output Type
        export_formats = ["IDS", "CSV", "PNG"]
        self.export_format = pn.widgets.RadioBoxGroup(
            name="Export Format",
            options=export_formats,
            value=export_formats[0],
            inline=True,
        )
        self.time_source = pn.widgets.RadioBoxGroup(
            name="Time Basis",
            options=["Linspace", "CSV File", "Manual"],
            value="Linspace",
        )
        self.input = pn.widgets.TextInput()
        output_option_box = pn.WidgetBox(
            pn.pane.Markdown("### 📤 Output type"),
            self.export_format,
            self.input,
            sizing_mode="stretch_width",
            margin=(10, 5),
        )

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
            pn.Row(
                self.time_source,
                self.linspace_row,
                self.csv_file_input,
                self.time_manual_input,
            ),
            sizing_mode="stretch_width",
            margin=(10, 5),
        )

        export_button = pn.widgets.Button(name="Export", button_type="primary")
        cancel_button = pn.widgets.Button(name="Cancel")

        layout = pn.Column(
            pn.pane.Markdown("## Export Configuration"),
            output_option_box,
            time_options_box,
            pn.Row(export_button, cancel_button),
            sizing_mode="stretch_width",
        )
        self.modal = pn.Modal(layout, width=600, height=500)

        # Callbacks
        self.export_format.param.watch(self._update_ui, "value")
        self.time_source.param.watch(self._update_ui, "value")
        export_button.on_click(self._handle_export)
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
        if value == "Linspace":
            self.linspace_row.visible = True
            self.csv_file_input.visible = False
            self.time_manual_input.visible = False
        elif value == "CSV File":
            self.linspace_row.visible = False
            self.csv_file_input.visible = True
            self.time_manual_input.visible = False
        elif value == "Manual":
            self.linspace_row.visible = False
            self.csv_file_input.visible = False
            self.time_manual_input.visible = True

        # Add Default option to PNG export
        if self.export_format.value == "PNG":
            if "Default" not in options:
                options.append("Default")
            if self.time_source.value == "Default":
                self.linspace_row.visible = False
                self.csv_file_input.visible = False
                self.time_manual_input.visible = False
        else:
            if "Default" in options:
                options.remove("Default")
                if self.time_source.value == "Default":
                    self.time_source.value = self.time_source.options[0]

        self.time_source.param.trigger("options")

    def _get_times(self):
        """Parse inputs and return the time array."""
        if self.time_source.value == "Linspace":
            return np.linspace(
                self.linspace_start.value,
                self.linspace_stop.value,
                self.linspace_num.value,
            )
        elif self.time_source.value == "CSV File":
            if not self.csv_file_input.value:
                raise ValueError("Please select a CSV file for the time basis.")
            try:
                return times_from_csv(self.csv_file_input.value, from_file_path=False)
            except Exception as e:
                raise ValueError(f"Invalid time CSV file.\n{e}") from e
        elif self.time_source.value == "Manual":
            return np.fromstring(self.time_manual_input.value, sep=",")

    def _handle_export(self, event):
        """Perform the export based on current settings."""
        self._close()
        input = self.input.value
        notification = pn.state.notifications.info(
            f"Exporting to {input}...", duration=0
        )
        try:
            if self.time_source.value != "Default":
                times = self._get_times()
                exporter = ConfigurationExporter(self.main_gui.config, times)
            else:
                exporter = ConfigurationExporter(self.main_gui.config, None)

            export_type = self.export_format.value
            if not input:
                pn.state.notifications.error("Please provide an output location.")
                return

            if export_type == "IDS":
                exporter.to_ids(input)
            elif export_type == "PNG":
                exporter.to_png(Path(input))
            elif export_type == "CSV":
                exporter.to_csv(Path(input))
            pn.state.notifications.success("Succesfully exported configuration")
        except Exception as e:
            pn.state.notifications.error(f"Export failed!\n{e}")

        # Destroy exporting notification once exporting is finished
        notification.destroy()

    def open(self, event):
        """Open the export modal dialog."""
        self._update_ui()
        self.modal.show()

    def _close(self, event=None):
        """Close the export modal dialog."""
        self.modal.hide()

    def __panel__(self):
        return self.modal
