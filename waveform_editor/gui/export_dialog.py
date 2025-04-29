import csv
import io
import logging
from pathlib import Path

import numpy as np
import panel as pn

from waveform_editor.exporter import ConfigurationExporter

logger = logging.getLogger(__name__)


class ExportDialog:
    """Handles the UI and logic for exporting waveform configurations."""

    def __init__(self, gui_ref):
        """
        Initialize the Export Dialog.

        Args:
            gui_ref: A reference to the main WaveformEditorGui instance.
        """
        self.gui = gui_ref  # Reference to access config and notifications

        export_formats = ["IDS", "CSV", "PNG"]

        self.export_format = pn.widgets.RadioButtonGroup(
            name="Export Format",
            options=export_formats,
            value=export_formats[0],
        )
        self.time_source = pn.widgets.RadioButtonGroup(
            name="Time Basis",
            options=["Linspace", "CSV File"],
            value="Linspace",
        )

        # Linspace inputs
        self.linspace_start = pn.widgets.FloatInput(name="Start", value=0.0, width=100)
        self.linspace_stop = pn.widgets.FloatInput(name="Stop", value=1.0, width=100)
        self.linspace_num = pn.widgets.IntInput(
            name="Num Points", value=101, step=1, start=2, width=100
        )
        self.linspace_row = pn.Row(
            self.linspace_start, self.linspace_stop, self.linspace_num, visible=True
        )

        # CSV input
        self.csv_file_input = pn.widgets.FileInput(
            name="Time CSV File", accept=".csv", visible=False
        )

        # Output path inputs (dynamically shown)
        self.uri_input = pn.widgets.TextInput(
            name="Output IDS URI",
            placeholder="e.g. imas:hdf5?path=testdb",
            visible=(self.export_format.value == "IDS"),
        )
        self.output_dir_input = pn.widgets.TextInput(
            name="Output Directory (PNG)",
            placeholder="e.g. /path/to/export/pngs",
            visible=(self.export_format.value == "PNG"),
        )
        self.output_csv_input = pn.widgets.TextInput(
            name="Output CSV File",
            placeholder="e.g. /path/to/export/output.csv",
            visible=(self.export_format.value == "CSV"),
        )

        self.export_button = pn.widgets.Button(name="Export", button_type="primary")
        self.cancel_button = pn.widgets.Button(name="Cancel")

        # --- Layout ---
        self.output_options = pn.Column(
            self.uri_input, self.output_dir_input, self.output_csv_input
        )
        self.layout = pn.Column(
            pn.pane.Markdown("### Export Configuration"),
            self.export_format,
            self.time_source,
            self.linspace_row,
            self.csv_file_input,
            pn.pane.Markdown("### Output"),
            self.output_options,
            pn.Row(self.export_button, self.cancel_button),
            sizing_mode="stretch_width",
        )

        self.modal = pn.Modal(
            self.layout,
            width=600,
            height=500,  # Adjust as needed
        )

        # --- Callbacks ---
        self.export_format.param.watch(self._update_ui, "value")
        self.time_source.param.watch(self._update_ui, "value")
        self.export_button.on_click(self._handle_export)
        self.cancel_button.on_click(self._close)

    def _update_ui(self, event=None):
        """Update visibility of widgets based on selections."""
        # Time source visibility
        is_linspace = self.time_source.value == "Linspace"
        self.linspace_row.visible = is_linspace
        self.csv_file_input.visible = not is_linspace

        # Output path visibility
        export_type = self.export_format.value
        self.uri_input.visible = export_type == "IDS"
        self.output_dir_input.visible = export_type == "PNG"
        self.output_csv_input.visible = export_type == "CSV"

    def _get_times(self):
        """Parse inputs and return the time array or None on error."""
        if self.time_source.value == "Linspace":
            start = self.linspace_start.value
            stop = self.linspace_stop.value
            num = self.linspace_num.value
            if num < 2:
                pn.state.notifications.error(
                    "Linspace 'Num Points' must be at least 2."
                )
                return None
            if start >= stop and num > 1:
                pn.state.notifications.warning(
                    "Linspace 'Start' is greater than or equal to 'Stop'."
                )
                # Allow it, but warn
            try:
                return np.linspace(start, stop, num)
            except Exception as e:
                pn.state.notifications.error(f"Error creating linspace: {e}")
                return None

        elif self.time_source.value == "CSV File":
            if not self.csv_file_input.value:
                pn.state.notifications.error(
                    "Please select a CSV file for the time basis."
                )
                return None
            try:
                content = self.csv_file_input.value.decode("utf-8")
                # Use csv reader for robustness
                reader = csv.reader(io.StringIO(content))
                rows = list(reader)

                if not rows:
                    raise ValueError("CSV file is empty.")
                if len(rows) > 1:
                    pn.state.notifications.warning(
                        "CSV file has multiple rows. Only the first row will be used for time values."
                    )

                # Parse the first row into floats
                time_array = [
                    float(value.strip()) for value in rows[0] if value.strip()
                ]
                if not time_array:
                    raise ValueError(
                        "No valid numeric values found in the first row of the CSV."
                    )

                return np.array(time_array)

            except Exception as e:
                pn.state.notifications.error(
                    f"Invalid time CSV file. Ensure it contains a single row of comma-separated numbers.\nDetails: {e}",
                    duration=8000,
                )
                return None
        else:
            # Should not happen with RadioButtonGroup
            pn.state.notifications.error("Invalid time source selected.")
            return None

    def _handle_export(self, event):
        """Perform the export based on current settings."""
        times = self._get_times()
        if times is None:
            return

        config = self.gui.config
        if not config or not config.waveform_map:
            pn.state.notifications.warning("No waveforms loaded or defined to export.")
            return

        exporter = ConfigurationExporter(config, times)
        export_type = self.export_format.value

        if export_type == "IDS":
            uri = self.uri_input.value
            if not uri:
                pn.state.notifications.error("Please provide an Output IDS URI.")
                return
            pn.state.notifications.info(
                f"Starting IDS export to {uri}...", duration=3000
            )
            exporter.to_ids(uri)

        elif export_type == "PNG":
            output_dir = self.output_dir_input.value
            if not output_dir:
                pn.state.notifications.error(
                    "Please provide an Output Directory for PNGs."
                )
                return
            pn.state.notifications.info(
                f"Starting PNG export to {output_dir}...", duration=3000
            )
            exporter.to_png(Path(output_dir))

        elif export_type == "CSV":
            output_csv = self.output_csv_input.value
            if not output_csv:
                pn.state.notifications.error("Please provide an Output CSV File path.")
                return
            pn.state.notifications.info(
                f"Starting CSV export to {output_csv}...", duration=3000
            )
            exporter.to_csv(Path(output_csv))

        self._close()

    def open(self, event):
        """Open the export modal dialog."""
        self._update_ui()
        self.modal.show()

    def _close(self, event=None):
        """Close the export modal dialog."""
        self.modal.hide()

    def __panel__(self):
        return self.modal
