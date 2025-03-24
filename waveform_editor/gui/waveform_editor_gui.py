import holoviews as hv
import panel as pn
import yaml

from waveform_editor.gui.waveform_plotter import WaveformPlotter

# TODO: bokeh is used since there are issues with the plotting when deselecting using
# plotly. Bokeh seems quite a bit slower than plotly, so it might be worth switching
# back to plotly later, or improve performance with bokeh
hv.extension("bokeh")


class WaveformEditor:
    def __init__(self, yaml_file):
        """Initialize the Waveform Editor Panel App"""
        with open(yaml_file) as f:
            yaml_data = yaml.safe_load(f)

        self.waveform_plotter = WaveformPlotter(yaml_data)
        self.waveform_selector = self.create_waveform_selector(yaml_data)

        self.waveform_plot = hv.DynamicMap(
            self.waveform_plotter.update_plot,
            streams=[self.waveform_plotter.param.selected_keys],
        )

        self.template = pn.template.MaterialTemplate(
            title="Waveform Editor (Draft version)",
            sidebar=[self.waveform_selector],
            main=pn.Column(
                pn.pane.Markdown("# Waveform Inspector"), self.waveform_plot
            ),
        )

    def create_waveform_selector(self, data):
        """Recursively create a Panel UI structure from the YAML"""
        categories = []
        options = []

        for key, value in data.items():
            if key == "globals":
                continue
            elif "/" in key:
                options.append(key)
            else:
                categories.append((key, self.create_waveform_selector(value)))

        content = []
        if options:
            check_buttons = pn.widgets.CheckButtonGroup(
                value=[],
                options=options,
                button_style="outline",
                button_type="primary",
                sizing_mode="stretch_width",
                orientation="vertical",
                stylesheets=["button {text-align: left!important;}"],
            )

            # TODO: You can currently only view selected waveforms together when they
            # are in the same group.
            def on_select(event):
                self.waveform_plotter.selected_keys = event.new

            check_buttons.param.watch(on_select, "value")
            content.append(check_buttons)

        if categories:
            accordion = pn.Accordion(*categories)
            content.append(accordion)

        return pn.Column(*content, sizing_mode="stretch_width")

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Main
yaml_file = "waveform_editor/test.yaml"
WaveformEditor(yaml_file).serve()
