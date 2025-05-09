import io

import holoviews as hv
import panel as pn

import waveform_editor
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.gui.editor import WaveformEditor
from waveform_editor.gui.export_dialog import ExportDialog
from waveform_editor.gui.plotter import WaveformPlotter
from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.selector import WaveformSelector
from waveform_editor.gui.start_up import StartUpPrompt

hv.extension("plotly")
pn.extension("plotly", "modal", "codeeditor", notifications=True)


class WaveformEditorGui:
    VIEW_WAVEFORMS_TAB = 0
    EDIT_WAVEFORMS_TAB = 1

    def __init__(self):
        """Initialize the Waveform Editor Panel App"""
        self.config = WaveformConfiguration()

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

        self.export_button = pn.widgets.Button(
            name="Export Data",
            icon="upload",
            button_type="primary",
            visible=False,
            align="end",
            width=150,
            margin=(5, 5),
        )
        export_dialog = ExportDialog(self)
        self.export_button.on_click(export_dialog.open)

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
        self.start_up = StartUpPrompt(self)

        # Append to sidebar to make the content of the sidebar dynamic
        sidebar_column = pn.Column(
            self.start_up,
            pn.Row(self.file_download, self.export_button),
            self.selector,
            self.modal,
            export_dialog,
        )
        self.template.sidebar.append(sidebar_column)

    def load_yaml(self, event):
        """Load waveform configuration from a YAML file.

        Args:
            event: The event object containing the uploaded file data.
        """

        self.plotter.plotted_waveforms = {}
        yaml_content = event.new.decode("utf-8")
        self.config.parser.load_yaml(yaml_content)

        if self.config.load_error:
            pn.state.notifications.error(
                f"YAML could not be loaded:\n{self.config.load_error}", duration=10000
            )
            self.make_ui_visible(False)
            return

        self.make_ui_visible(True)

        # Create tree structure in sidebar based on waveform groups in YAML
        self.selector.create_waveform_selector_ui()

        if self.start_up.file_input.filename:
            new_filename = self.start_up.file_input.filename.replace(
                ".yaml", "-new.yaml"
            )
            self.file_download.filename = new_filename

    def make_ui_visible(self, is_visible):
        """
        Toggles the visibility of UI elements based on the given flag.

        Args:
            is_visible: If True, makes certain UI elements visible, else hides them.
        """
        self.tabs.visible = is_visible
        self.file_download.visible = is_visible
        self.export_button.visible = is_visible
        self.start_up.visible = not is_visible
        self.selector.ui_selector.visible = is_visible

    def save_yaml(self):
        """Generate and return the YAML file as a BytesIO object"""
        yaml_str = self.config.dump()
        return io.BytesIO(yaml_str.encode("utf-8"))

    def __panel__(self):
        return self.template

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Run the app
WaveformEditorGui().serve()
