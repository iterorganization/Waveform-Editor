import panel as pn

from waveform_editor.yaml_parser import YamlParser


class WaveformEditor:
    """A Panel interface for waveform editing."""

    def __init__(self, plotter, config):
        self.plotter = plotter
        self.config = config
        self.path = []
        self.waveform = None

        # Code editor UI
        self.yaml_alert = pn.pane.Alert(
            "### The YAML did not parse correctly!",
            alert_type="danger",
            visible=False,
        )
        self.error_alert = pn.pane.Alert(
            "### There was an error in the YAML configuration.",
            alert_type="warning",
            visible=False,
        )
        self.code_editor = pn.widgets.CodeEditor(
            sizing_mode="stretch_both",
            language="yaml",
        )
        self.code_editor.param.watch(self.on_value_change, "value")
        self.set_default()

        save_button = pn.widgets.ButtonIcon(
            icon="device-floppy",
            size="30px",
            active_icon="check",
            description="Save waveform",
        )
        save_button.on_click(self.save_waveform)

        self.layout = pn.Column(
            save_button, self.code_editor, self.yaml_alert, self.error_alert
        )

    def on_value_change(self, event):
        """Update the plot based on the YAML editor input.

        Args:
            event: Event containing the code editor value input.
        """
        value = event.new
        yaml_parser = YamlParser()
        self.yaml_alert.visible = self.error_alert.visible = False
        self.waveform = yaml_parser.parse_waveforms(value)
        annotations = self.waveform.annotations

        self.code_editor.annotations = list(annotations)
        self.code_editor.param.trigger("annotations")

        if yaml_parser.has_yaml_error:
            self.yaml_alert.object = (
                f"### The YAML did not parse correctly\n {annotations}"
            )
            self.yaml_alert.visible = True
        elif self.code_editor.annotations:
            self.error_alert.object = (
                f"### There was an error in the YAML configuration\n {annotations}"
            )
            self.error_alert.visible = True

        self.plotter.plotted_waveforms = [self.waveform]

    def set_default(self):
        """Set code editor value to default."""
        self.code_editor.value = "empty_waveform: {}"

    def save_waveform(self, event=None):
        """Store the waveform into the WaveformConfiguration at the location determined
        by self.path."""
        if self.yaml_alert.visible or self.error_alert.visible:
            pn.state.notifications.error("Cannot save YAML with errors.")
            return

        if self.waveform.name in self.config.waveform_map:
            if not self.path:
                raise ValueError("The path in the waveform editor was not set.")
            self.config.add_waveform(self.waveform, self.path)
            pn.state.notifications.success("Succesfully saved waveform!")
        else:
            pn.state.notifications.error(
                f"Error: `{self.waveform.name}` not found in YAML", duration=5000
            )

    def get(self):
        """Return the editor panel UI."""
        return self.layout
