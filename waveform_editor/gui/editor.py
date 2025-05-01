import panel as pn
from panel.viewable import Viewer


class WaveformEditor(Viewer):
    """A Panel interface for waveform editing."""

    def __init__(self, plotter, config):
        self.plotter = plotter
        self.config = config
        self.waveform = None

        # Code editor UI
        self.error_alert = pn.pane.Alert(visible=False)
        self.code_editor = pn.widgets.CodeEditor(
            sizing_mode="stretch_both", language="yaml"
        )
        self.code_editor.param.watch(self.on_value_change, "value")
        self.set_empty()

        save_button = pn.widgets.ButtonIcon(
            icon="device-floppy",
            size="30px",
            active_icon="check",
            description="Save waveform",
        )
        save_button.on_click(self.save_waveform)

        self.layout = pn.Column(save_button, self.code_editor, self.error_alert)

    def on_value_change(self, event):
        """Update the plot based on the YAML editor input.

        Args:
            event: Event containing the code editor value input.
        """
        if not self.plotter.plotted_waveforms:
            return
        editor_text = event.new

        if len(self.plotter.plotted_waveforms) != 1:
            raise ValueError("The plotter may only have a single waveform selected.")

        # Fetch name from selected waveform
        name = next(iter(self.plotter.plotted_waveforms))

        # Merge code editor string with name into a single yaml string
        if editor_text.lstrip().startswith("- "):
            waveform_yaml = f"{name}:\n{editor_text}"
        else:
            waveform_yaml = f"{name}: {editor_text}"
        self.waveform = self.config.parse_waveform(waveform_yaml)
        annotations = self.waveform.annotations

        self.code_editor.annotations = list(annotations)

        if self.config.parser.parse_errors:
            self.error_alert.object = (
                "### The YAML did not parse correctly\n  "
                f"{self.config.parser.parse_errors[0]}"
            )
            self.error_alert.alert_type = "danger"
            self.error_alert.visible = True
        elif self.code_editor.annotations:
            self.error_alert.object = (
                f"### There was an error in the YAML configuration\n{annotations}"
            )
            self.error_alert.alert_type = "warning"
            self.error_alert.visible = True
        else:
            self.error_alert.visible = False

        # Only update plot when there are no YAML errors
        if not self.config.parser.parse_errors:
            self.plotter.plotted_waveforms = {self.waveform.name: self.waveform}

    def set_empty(self):
        """Set code editor value to empty value in read-only mode."""
        self.code_editor.value = "Select a waveform to edit"
        self.code_editor.readonly = True
        self.error_alert.visible = False
        self.plotter.title = ""
        self.plotter.param.trigger("plotted_waveforms")

    def save_waveform(self, event=None):
        """Store the waveform into the WaveformConfiguration at the location determined
        by self.path."""
        if self.error_alert.visible:
            pn.state.notifications.error("Cannot save YAML with errors.")
            return

        if self.waveform.name in self.config.waveform_map:
            self.config.replace_waveform(self.waveform)
            # TODO: Sometimes notifications seem to not be shown, even when this is
            # called, should be investigated
            pn.state.notifications.success("Succesfully saved waveform!")
        else:
            pn.state.notifications.error(
                f"Error: `{self.waveform.name}` not found in YAML"
            )

    def __panel__(self):
        """Return the editor panel UI."""
        return self.layout
