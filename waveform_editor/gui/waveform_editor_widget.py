import holoviews as hv
import panel as pn
import yaml

from waveform_editor.gui.waveform_plotter import WaveformPlotter
from waveform_editor.yaml_parser import YamlParser


class WaveformEditor:
    """A Panel interface for waveform editing and live plotting."""

    def __init__(self, yaml, yaml_map):
        self.yaml = yaml
        self.yaml_map = yaml_map

        self.yaml_parser = YamlParser()
        self.waveform = None

        # TODO: Decide on size, or dynamically scale UI based on screen resolution?
        self.code_editor = pn.widgets.CodeEditor(
            value="empty_waveform: {}",
            width=600,
            height=1200,
            language="yaml",
        )

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

        plot = hv.DynamicMap(
            pn.bind(self.update_plot, value=self.code_editor.param.value)
        )

        self.layout = pn.Row(
            pn.Column(self.save_button, self.code_editor),
            pn.Column(plot, self.yaml_alert, self.error_alert),
        )

    def update_plot(self, value, width=1200, height=800):
        """Update the plot based on the YAML editor input.

        Args:
            value: Value of the code editor.
            width: Width of the plot in pixels.
            height: Height of the plot in pixels.
        """
        self.yaml_alert.visible = self.error_alert.visible = False
        self.waveform = self.yaml_parser.parse_waveforms(value)
        annotations = self.yaml_parser.waveform.annotations

        self.code_editor.annotations = list(annotations)
        self.code_editor.param.trigger("annotations")

        # Show alert when there is a yaml parsing error
        if self.yaml_parser.has_yaml_error:
            self.yaml_alert.object = (
                f"### The YAML did not parse correctly\n {annotations}"
            )
            self.yaml_alert.visible = True
        elif self.code_editor.annotations:
            self.error_alert.object = (
                f"### There was an error in the YAML configuration\n {annotations}"
            )
            self.error_alert.visible = True

        waveform_plotter = WaveformPlotter()

        return waveform_plotter.plot_tendencies(self.waveform, "").opts(
            width=width, height=height
        )

    def save_waveform(self, event=None):
        """Search for the waveform name in the nested YAML structure and replace its
        value."""

        name = self.waveform.name
        new_value = yaml.safe_load(self.code_editor.value).get(name, None)

        # Search for name as key in the yaml file and update the yaml, as well as the
        # YAML map if it exists
        if self._search_and_replace(self.yaml, name, new_value):
            self.yaml_map[name] = new_value
            pn.state.notifications.success("Succesfully saved waveform!")
        else:
            pn.state.notifications.error(
                f"Error: `{name}` not found in YAML", duration=5000
            )

    def _search_and_replace(self, d, key, new_value):
        """Recursively search for a key in a nested dictionary and replace its value."""
        if isinstance(d, dict):
            for k, v in d.items():
                if k == key:
                    d[k] = new_value
                    return True
                elif isinstance(v, dict):
                    if self._search_and_replace(v, key, new_value):
                        return True
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and self._search_and_replace(
                            item, key, new_value
                        ):
                            return True
        return False

    def get(self):
        """Return the Panel layout for integration into the main GUI."""
        return self.layout
