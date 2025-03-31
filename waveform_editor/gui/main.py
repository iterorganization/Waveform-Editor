import io

import holoviews as hv
import panel as pn
import yaml

import waveform_editor
from waveform_editor.gui.waveform_editor_widget import WaveformEditor
from waveform_editor.gui.waveform_plotter import WaveformPlotter
from waveform_editor.gui.waveform_selector.waveform_selector import WaveformSelector

# TODO: bokeh is used since there are issues with the plotting when deselecting using
# plotly. Bokeh seems quite a bit slower than plotly, so it might be worth switching
# back to plotly later, or improve performance with bokeh
hv.extension("bokeh")
pn.extension(notifications=True)
pn.extension("codeeditor")


class WaveformEditorGui:
    def __init__(self):
        """Initialize the Waveform Editor Panel App"""
        # The parsed YAML file
        self.yaml = {}
        # Waveform mapping for all waveforms in the YAML file. The keys are the waveform
        # names, and the values are the parsed YAML content.
        self.yaml_map = {}

        self.editor = WaveformEditor(self.yaml, self.yaml_map)
        self.waveform_plotter = WaveformPlotter()
        self.waveform_selector = WaveformSelector(
            self.yaml, self.yaml_map, self.waveform_plotter, self.editor
        )

        self.file_input = pn.widgets.FileInput(accept=".yaml")
        self.file_input.param.watch(self.load_yaml, "value")
        # TODO: The file download button is a placeholder for the actual saving
        # behavior, which should be implemented later
        self.file_download = pn.widgets.FileDownload(
            callback=self.save_yaml,
            icon="download",
            filename="output.yaml",
            button_type="primary",
            auto=True,
            visible=False,
        )

        self.tabs = pn.Tabs(dynamic=True)
        self.tabs.param.watch(self.on_tab_change, "active")

        self.template = pn.template.FastListTemplate(
            title=f"Waveform Editor (v{waveform_editor.__version__})",
            main=self.tabs,
            sidebar_width=400,
        )

        self.sidebar_column = pn.Column(
            self.file_download,
            pn.pane.Markdown("## Select Waveform Editor YAML File", margin=0),
            self.file_input,
            self.waveform_selector.get(),
        )
        self.template.sidebar.append(self.sidebar_column)

    def on_tab_change(self, event):
        """Change selection behavior of the waveform selector, depending on which tab
        is selected."""
        self.waveform_selector.deselect_all()
        if event.new == 1:
            self.waveform_selector.edit_waveforms_enabled = True
        else:
            self.waveform_selector.edit_waveforms_enabled = False

    def load_yaml(self, event):
        """Load YAML data from uploaded file."""
        self.file_download.visible = True
        yaml_content = event.new.decode("utf-8")
        self.yaml = yaml.safe_load(yaml_content)

        self.editor = WaveformEditor(self.yaml, self.yaml_map)
        self.tabs[:] = [
            ("View Waveforms", self.waveform_plotter.get()),
            ("Edit Waveforms", self.editor.get()),
        ]
        self.waveform_selector = WaveformSelector(
            self.yaml, self.yaml_map, self.waveform_plotter, self.editor
        )
        self.sidebar_column[1] = pn.pane.Markdown(
            f"## Successfully loaded `{self.file_input.filename}`", margin=0
        )
        self.sidebar_column[3] = self.waveform_selector.get()

        if self.file_input.filename:
            new_filename = self.file_input.filename.replace(".yaml", "-new.yaml")
            self.file_download.filename = new_filename

    def save_yaml(self):
        """Generate and return the YAML file as a BytesIO object"""
        yaml_str = yaml.dump(self.yaml, default_flow_style=False)
        return io.BytesIO(yaml_str.encode("utf-8"))

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Run the app
WaveformEditorGui().serve()
