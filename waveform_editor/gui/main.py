import io

import panel as pn
import param

import waveform_editor
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.gui.editor import WaveformEditor
from waveform_editor.gui.export_dialog import ExportDialog
from waveform_editor.gui.plotter_edit import PlotterEdit
from waveform_editor.gui.plotter_view import PlotterView
from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.selector import WaveformSelector
from waveform_editor.gui.start_up import StartUpPrompt
from waveform_editor.util import State

# Note: these extension() calls take a couple of seconds
# Please avoid importing this module unless actually starting the GUI
pn.extension("modal", "codeeditor", notifications=True)


class WaveformEditorGui(param.Parameterized):
    VIEW_WAVEFORMS_TAB = 0
    EDIT_WAVEFORMS_TAB = 1

    DISCARD_CHANGES_MESSAGE = (
        "# **⚠️ Warning**  \nYou did not save your changes. "
        "Leaving now will discard any changes you made to this waveform."
        "   \n\n**Are you sure you want to continue?**"
    )

    show_startup_options = param.Boolean(True)

    def __init__(self):
        """Initialize the Waveform Editor Panel App"""
        super().__init__()
        self._reverting_to_editor = State()

        self.config = WaveformConfiguration()

        # TODO: The file download button is a placeholder for the actual saving
        # behavior, which should be implemented later
        self.file_download = pn.widgets.FileDownload(
            callback=self.save_yaml,
            icon="download",
            filename="output.yaml",
            button_type="primary",
            auto=True,
            visible=self.param.show_startup_options.rx.not_(),
        )

        export_dialog = ExportDialog(self)
        self.export_button = pn.widgets.Button(
            name="Export waveforms",
            icon="upload",
            button_type="primary",
            visible=self.param.show_startup_options.rx.not_(),
            align="end",
            width=150,
            margin=(5, 5),
            on_click=export_dialog.open,
        )

        # Side bar
        self.modal = ConfirmModal()
        self.selector = WaveformSelector(self)
        self.selector.visible = self.param.show_startup_options.rx.not_()
        self.selector.param.watch(self.on_selection_change, "selection")
        self.start_up = StartUpPrompt(self, visible=self.param.show_startup_options)
        sidebar = pn.Column(
            self.start_up,
            pn.Row(self.file_download, self.export_button),
            self.selector,
            self.modal,
            export_dialog,
        )

        # Main views: view and edit tabs
        self.editor = WaveformEditor(self.config)
        self.plotter_view = PlotterView()
        self.plotter_edit = PlotterEdit(self.editor)
        self.tabs = pn.Tabs(
            ("View Waveforms", self.plotter_view),
            ("Edit Waveforms", pn.Row(self.editor, self.plotter_edit)),
            dynamic=True,
            visible=self.param.show_startup_options.rx.not_(),
        )
        self.tabs.param.watch(self.on_tab_change, "active")

        # Set multiselect property of the selector based on the active tab:
        allow_multiselect = self.tabs.param.active.rx() == self.VIEW_WAVEFORMS_TAB
        self.selector.multiselect = allow_multiselect

        # Combined UI:
        self.template = pn.template.FastListTemplate(
            title=f"Waveform Editor (v{waveform_editor.__version__})",
            main=self.tabs,
            sidebar=sidebar,
            sidebar_width=400,
        )

    def on_selection_change(self, event):
        """Respond to a changed waveform selection"""
        if self._reverting_to_editor:
            return  # ignore this event when we revert to the editor
        if (
            self.tabs.active == self.EDIT_WAVEFORMS_TAB
            and self.editor.has_changed()
            # Check if current waveform is being removed. The user already confirmed
            # they want to remove the waveform, so we don't ask again:
            and not self.selector.is_removing_waveform
        ):
            self.modal.show(
                self.DISCARD_CHANGES_MESSAGE,
                on_confirm=self.update_selection,
                on_cancel=self.revert_to_editor,
            )
        else:
            self.update_selection()

    def on_tab_change(self, event):
        """Respond to a tab change"""
        if self._reverting_to_editor:
            return  # ignore this event when we revert to the editor
        if event.old == self.EDIT_WAVEFORMS_TAB and self.editor.has_changed():
            self.modal.show(
                self.DISCARD_CHANGES_MESSAGE,
                on_confirm=self.update_selection,
                on_cancel=self.revert_to_editor,
            )
        else:
            self.update_selection()

    def update_selection(self):
        """Reflect updated selection in other components"""
        selection = self.selector.selection
        if self.tabs.active == self.EDIT_WAVEFORMS_TAB:
            self.editor.set_waveform(None if not selection else selection[0])
            self.plotter_view.plotted_waveforms = {}
        elif self.tabs.active == self.VIEW_WAVEFORMS_TAB:
            self.editor.set_waveform(None)
            waveform_map = {name: self.config[name] for name in selection}
            self.plotter_view.plotted_waveforms = waveform_map

    def revert_to_editor(self):
        """Revert to the editor without changing its contents"""
        with self._reverting_to_editor:  # Disable watchers for tab and selection
            self.tabs.active = self.EDIT_WAVEFORMS_TAB
            self.selector.set_selection([self.editor.waveform.name])

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
            self.show_startup_options = True
            return

        self.show_startup_options = False

        # Create tree structure in sidebar based on waveform groups in YAML
        self.selector.refresh()

        if self.start_up.file_input.filename:
            new_filename = self.start_up.file_input.filename.replace(
                ".yaml", "-new.yaml"
            )
            self.file_download.filename = new_filename

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
