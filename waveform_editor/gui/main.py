import holoviews as hv
import panel as pn
import yaml

import waveform_editor
from waveform_editor.gui.waveform_editor_widget import WaveformEditor
from waveform_editor.gui.waveform_plotter import WaveformPlotter
from waveform_editor.gui.waveform_selector import WaveformSelector

# TODO: bokeh is used since there are issues with the plotting when deselecting using
# plotly. Bokeh seems quite a bit slower than plotly, so it might be worth switching
# back to plotly later, or improve performance with bokeh
hv.extension("bokeh")


class WaveformEditorGui:
    def __init__(self, yaml_file):
        """Initialize the Waveform Editor Panel App"""
        with open(yaml_file) as f:
            yaml_data = yaml.safe_load(f)

        editor = WaveformEditor()
        waveform_plotter = WaveformPlotter(yaml_data)
        waveform_selector = WaveformSelector(yaml_data, waveform_plotter, editor)

        # Tabs to handle the "View" and "Edit" tabs
        tabs = pn.Tabs(
            ("View Waveforms", waveform_plotter.get_dynamic_map()),
            ("Edit Waveforms", editor.get_layout()),
            dynamic=True,
        )

        def on_tab_change(event):
            # Check if "Edit Waveforms" tab is selected (index 1)
            if event.new == 1:
                waveform_selector.deselect_all()
                waveform_selector.enable_deselect_logic(True)
            else:
                waveform_selector.enable_deselect_logic(False)

        tabs.param.watch(on_tab_change, "active")

        sidebar = pn.Column(
            pn.pane.Markdown(f"## File: `{yaml_file}`", margin=0),
            waveform_selector.get_selector(),
        )

        self.template = pn.template.FastListTemplate(
            title=f"Waveform Editor (v{waveform_editor.__version__})",
            sidebar=sidebar,
            main=tabs,
            sidebar_width=400,
        )

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Run the app
yaml_file = "waveform_editor/test.yaml"
WaveformEditorGui(yaml_file).serve()
