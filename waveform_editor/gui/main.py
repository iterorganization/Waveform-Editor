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
        """Initialize the Waveform Editor Panel App"""
        self.file_input = pn.widgets.FileInput(accept=".yaml")
        self.file_input.param.watch(self.load_yaml, "value")

        self.tabs = pn.Tabs(dynamic=True)
        self.template = pn.template.FastListTemplate(
            title=f"Waveform Editor (v{waveform_editor.__version__})",
            main=self.tabs,
            sidebar_width=400,
        )
        # To update the sidebar we wrap it into a panel column object and update this.
        # This trick is taken from:
        # https://discourse.holoviz.org/t/callbacks-to-update-widgets-in-bootstrap-
        # template-sidebar-based-on-active-tab/1535/2
        self.sidebar_column = pn.Column(
            pn.Column(
                pn.pane.Markdown("## Select YAML File", margin=0),
                self.file_input,
            )
        )
        self.template.sidebar.append(self.sidebar_column)

        # Change selection logic depending on which tab is selected
        def on_tab_change(event):
            # Check if "Edit Waveforms" tab is selected (index 1)
            if event.new == 1:
                self.waveform_selector.deselect_all()
                self.waveform_selector.enable_deselect_logic(True)
            else:
                self.waveform_selector.enable_deselect_logic(False)

        self.tabs.param.watch(on_tab_change, "active")

    def load_yaml(self, event):
        """Load YAML data from uploaded file"""
        yaml_content = event.new.decode("utf-8")
        self.yaml_data = yaml.safe_load(yaml_content)

        editor = WaveformEditor()
        self.waveform_plotter = WaveformPlotter(self.yaml_data)
        self.waveform_selector = WaveformSelector(
            self.yaml_data, self.waveform_plotter, editor
        )

        self.tabs[:] = [
            ("View Waveforms", self.waveform_plotter.get_dynamic_map()),
            ("Edit Waveforms", editor.get_layout()),
        ]

        self.sidebar_column[0] = pn.Column(
            pn.pane.Markdown(
                f"## Succesfully loaded `{self.file_input.filename}`", margin=0
            ),
            self.file_input,
            self.waveform_selector.get_selector(),
        )

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Run the app
WaveformEditorGui().serve()
