import holoviews as hv
import panel as pn

from waveform_editor.gui.waveform_plotter import WaveformPlotter
from waveform_editor.yaml_parser import YamlParser

pn.extension("codeeditor")


class WaveformEditor:
    """A separate class for the waveform editing interface with a YAML editor and live
    plotting."""

    def __init__(self):
        self.yaml_parser = YamlParser()

        # YAML Code Editor
        self.code_editor = pn.widgets.CodeEditor(
            value="""\
waveform:
- {type: linear, from: 0, to: 8, duration: 5}
- {type: sine-wave, base: 8, amplitude: 2, frequency: 1, duration: 4}
- {type: constant, value: 8, duration: 3}
- {type: smooth, from: 8, to: 0, duration: 2}
""",
            width=600,
            height=1200,
            theme="tomorrow",
            language="yaml",
        )

        # Error Alerts
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

        # Live Plot Updates
        self.plot = hv.DynamicMap(
            pn.bind(self.update_plot, value=self.code_editor.param.value)
        )
        self.plot_and_alert = pn.Column(self.plot, self.yaml_alert, self.error_alert)

        # Layout: Code Editor | Plot + Errors
        self.layout = pn.Row(self.code_editor, self.plot_and_alert)

    def update_plot(self, value, width=1200, height=800):
        """Update the plot based on the YAML editor input."""
        self.yaml_alert.visible = self.error_alert.visible = False
        waveform = self.yaml_parser.parse_waveforms(value)
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

        waveform_plotter = WaveformPlotter(value)

        return waveform_plotter.plot_tendencies(waveform, "asdf").opts(
            width=width, height=height
        )

    def get_layout(self):
        """Return the Panel layout for integration into the main GUI."""
        return self.layout
