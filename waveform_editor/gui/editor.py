import holoviews as hv
import panel as pn

from waveform_editor.yaml_parser import YamlParser


class WaveformEditor:
    """A Panel interface for waveform editing."""

    def __init__(self, plotter, config):
        self.plotter = plotter
        self.config = config
        self.path = []

        self.waveform = None

        self.code_editor = pn.widgets.CodeEditor(
            sizing_mode="stretch_both",
            language="yaml",
        )
        self.set_default()

        self.save_button = pn.widgets.ButtonIcon(
            icon="device-floppy",
            size="30px",
            active_icon="check",
            description="Save waveform",
        )
        self.save_button.on_click(self.save_waveform)

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

        self.code_editor.param.watch(self.on_value_change, "value")

        self.layout = pn.Column(
            self.save_button, self.code_editor, self.yaml_alert, self.error_alert
        )

    def on_value_change(self, event):
        """Update the plot based on the YAML editor input.

        Args:
            value: Value of the code editor.
            width: Width of the plot in pixels.
            height: Height of the plot in pixels.
        """
        value = event.new
        yaml_parser = YamlParser()
        self.yaml_alert.visible = self.error_alert.visible = False
        self.waveform = yaml_parser.parse_waveforms(value)
        annotations = self.waveform.annotations

        self.code_editor.annotations = list(annotations)
        self.code_editor.param.trigger("annotations")

        # Show alert when there is a yaml parsing error
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

        self.plotter.plotted_waveforms = {self.waveform.name: self.waveform}

    def set_default(self):
        """Set code editor value to default."""
        self.code_editor.value = "empty_waveform: {}"

    def save_waveform(self, event=None):
        """Search for the waveform name in the nested YAML structure and replace its
        value."""

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
        """Return the Panel layout for integration into the main GUI."""
        return self.layout
