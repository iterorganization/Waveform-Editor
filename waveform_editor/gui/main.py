import holoviews as hv
import panel as pn
import yaml

from waveform_editor.gui.waveform_editor_widget import WaveformEditor
from waveform_editor.gui.waveform_plotter import WaveformPlotter
from waveform_editor.gui.waveform_selector import WaveformSelector

# TODO: bokeh is used since there are issues with the plotting when deselecting using
# plotly. Bokeh seems quite a bit slower than plotly, so it might be worth switching
# back to plotly later, or improve performance with bokeh
hv.extension("bokeh")


class TemplateGUI:
    def __init__(self, yaml_file):
        """Initialize the Waveform Editor Panel App"""
        with open(yaml_file) as f:
            yaml_data = yaml.safe_load(f)

        self.waveform_plotter = WaveformPlotter(yaml_data)
        self.waveform_editor = WaveformEditor()
        self.waveform_selector = WaveformSelector(yaml_data, self.waveform_plotter)

        self.waveform_plot = hv.DynamicMap(
            self.waveform_plotter.update_plot,
            streams=[self.waveform_plotter.param.selected_keys],
        )

        main = pn.Tabs(
            pn.Column(self.waveform_plot, name="View Waveforms"),
            pn.Column(self.waveform_editor.get_layout(), name="Edit Waveforms"),
            pn.Column(name="Plasma shape editor"),
            dynamic=True,
        )
        self.template = pn.template.MaterialTemplate(
            title="Waveform Editor (Draft version)",
            sidebar=[self.waveform_selector.get_selector()],
            main=main,
        )

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Main
yaml_file = "waveform_editor/test.yaml"
TemplateGUI(yaml_file).serve()
