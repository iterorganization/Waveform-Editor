import io

import panel as pn

import waveform_editor
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.gui.editor import WaveformEditor
from waveform_editor.gui.export_dialog import ExportDialog
from waveform_editor.gui.plotter_edit import PlotterEdit
from waveform_editor.gui.plotter_view import PlotterView
from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.selector import WaveformSelector
from waveform_editor.gui.start_up import StartUpPrompt

# Note: these extension() calls take a couple of seconds
# Please avoid importing this module unless actually starting the GUI
pn.extension("modal", "codeeditor", notifications=True)


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
            name="Export waveforms",
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
        self.plotter_view = PlotterView()
        self.plotter_edit = PlotterEdit()
        self.editor = WaveformEditor(self.config)
        self.plotter_edit.plotted_waveform = self.editor.param.waveform
        self.selector = WaveformSelector(self)
        self.selector.param.watch(self.update_plotted_waveforms, "selection")
        self.tabs = pn.Tabs(
            ("View Waveforms", self.plotter_view),
            ("Edit Waveforms", pn.Row(self.editor, self.plotter_edit)),
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

    def update_plotted_waveforms(self, _):
        """Update plotter.plotted_waveforms whenever the selector.selection changes."""
        self.plotter_view.plotted_waveforms = {
            waveform: self.config[waveform] for waveform in self.selector.selection
        }
        if len(self.selector.selection) == 0:
            self.editor.set_waveform(None)
        else:
            waveform = self.selector.selection[0]
            self.editor.set_waveform(waveform)

    def load_yaml(self, event):
        """Load waveform configuration from a YAML file.

        Args:
            event: The event object containing the uploaded file data.
        """

        self.plotter_view.plotted_waveforms = {}
        yaml_content = event.new.decode("utf-8")
        self.config.parser.load_yaml(yaml_content)

        if self.config.load_error:
            pn.state.notifications.error(
                "YAML could not be loaded:<br>"
                + self.config.load_error.replace("\n", "<br>"),
                duration=10000,
            )
            self.make_ui_visible(False)
            return

        self.make_ui_visible(True)

        # Create tree structure in sidebar based on waveform groups in YAML
        self.selector.refresh()

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
        self.selector.visible = is_visible

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
