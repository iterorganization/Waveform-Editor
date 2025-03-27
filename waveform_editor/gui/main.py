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
    def __init__(self):
        """Initialize the Waveform self.Editor Panel App"""
        self.file_input = pn.widgets.FileInput(accept=".yaml")
        self.file_input.param.watch(self.load_yaml, "value")

        self.editor = WaveformEditor()
        self.waveform_plotter = WaveformPlotter()
        self.waveform_selector = WaveformSelector(
            {}, self.waveform_plotter, self.editor
        )

        self.tabs = pn.Tabs(dynamic=True)
        self.template = pn.template.FastListTemplate(
            title=f"Waveform Editor (v{waveform_editor.__version__})",
            main=self.tabs,
            sidebar_width=400,
        )
        self.tabs.param.watch(self.on_tab_change, "active")

        self.sidebar_column = pn.Column(
            pn.pane.Markdown("## Select Waveform Editor YAML File", margin=0),
            self.file_input,
            self.waveform_selector.get_selector(),
        )
        self.template.sidebar.append(self.sidebar_column)

    # Change selection logic depending on which tab is selected
    def on_tab_change(self, event):
        # Check if "Edit Waveforms" tab is selected
        if event.new == 1:
            self.waveform_selector.deselect_all()
            self.waveform_selector.edit_waveforms_enabled = True
        else:
            self.waveform_selector.edit_waveforms_enabled = False

    def load_yaml(self, event):
        """Load YAML data from uploaded file"""
        yaml_content = event.new.decode("utf-8")
        self.yaml_data = yaml.safe_load(yaml_content)

        self.tabs[:] = [
            ("View Waveforms", self.waveform_plotter.get_dynamic_map()),
            ("Edit Waveforms", self.editor.get_layout()),
        ]

        self.waveform_selector = WaveformSelector(
            self.yaml_data, self.waveform_plotter, self.editor
        )
        self.sidebar_column[0] = pn.pane.Markdown(
            f"## Succesfully loaded `{self.file_input.filename}`", margin=0
        )
        self.sidebar_column[2] = self.waveform_selector.get_selector()

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Run the app
WaveformEditorGui().serve()
