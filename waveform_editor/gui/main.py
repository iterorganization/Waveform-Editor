import io

import holoviews as hv
import panel as pn

import waveform_editor
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.gui.editor import WaveformEditor
from waveform_editor.gui.plotter import WaveformPlotter
from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.selector import WaveformSelector

# TODO: bokeh is used since there are issues with the plotting when deselecting using
# plotly. Bokeh seems quite a bit slower than plotly, so it might be worth switching
# back to plotly later, or improve performance with bokeh
hv.extension("bokeh")
pn.extension("modal", "codeeditor", notifications=True)


class WaveformEditorGui:
    def __init__(self):
        """Initialize the Waveform Editor Panel App"""
        self.config = WaveformConfiguration()

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

        # Add tabs to switch from viewer to editor
        self.modal = ConfirmModal()
        self.plotter = WaveformPlotter()
        self.editor = WaveformEditor(self.plotter, self.config)
        self.selector = WaveformSelector(self)
        self.tabs = pn.Tabs(
            ("View Waveforms", self.plotter),
            ("Edit Waveforms", pn.Row(self.editor, self.plotter)),
            dynamic=True,
            visible=False,
        )
        self.tabs.param.watch(self.selector.on_tab_change, "active")
        self.template = pn.template.FastListTemplate(
            title=f"Waveform Editor (v{waveform_editor.__version__})",
            main=self.tabs,
            sidebar_width=400,
        )
        self.sidebar_text = pn.pane.Markdown(
            "## Select Waveform Editor YAML File", margin=0
        )

        # Append to sidebar to make the content of the sidebar dynamic
        self.sidebar_column = pn.Column(
            self.file_download,
            self.sidebar_text,
            self.file_input,
            self.selector,
            self.modal,
        )
        self.template.sidebar.append(self.sidebar_column)

    def load_yaml(self, event):
        """Load waveform configuration from a YAML file.

        Args:
            event: The event object containing the uploaded file data.
        """

        self.plotter.plotted_waveforms = []
        yaml_content = event.new.decode("utf-8")
        self.config.load_yaml(yaml_content)

        if self.config.load_error:
            pn.state.notifications.error(
                f"YAML could not be loaded:\n{self.config.load_error}", duration=10000
            )
            self.make_ui_visible(False)
            return

        self.make_ui_visible(True)

        # Create tree structure in sidebar based on waveform groups in YAML
        self.selector.create_waveform_selector_ui()

        if self.file_input.filename:
            new_filename = self.file_input.filename.replace(".yaml", "-new.yaml")
            self.file_download.filename = new_filename

    def make_ui_visible(self, is_visible):
        """
        Toggles the visibility of UI elements based on the given flag.

        Args:
            is_visible: If True, makes certain UI elements visible, else hides them.
        """
        self.tabs.visible = is_visible
        self.file_download.visible = is_visible
        self.sidebar_text.visible = not is_visible
        self.selector.ui_selector.visible = is_visible

    def save_yaml(self):
        """Generate and return the YAML file as a BytesIO object"""
        yaml_str = self.config.to_yaml()
        return io.BytesIO(yaml_str.encode("utf-8"))

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Run the app
WaveformEditorGui().serve()
