from pathlib import Path

import panel as pn
import param

from waveform_editor.gui.selector.confirm_modal import ConfirmModal


class FileLoader(param.Parameterized):
    file_list = param.MultiFileSelector()
    error_alert = param.String()

    def __init__(self, manager):
        super().__init__()

        self.manager = manager
        self.main_gui = manager.main_gui

        self.file_selector = pn.widgets.FileSelector.from_param(
            self.param.file_list,
            directory=Path.cwd(),
            root_directory=Path.cwd().root,
            file_pattern="*.yaml",
            only_files=True,
        )

        alert = pn.pane.Alert(
            self.param.error_alert,
            alert_type="danger",
            visible=self.param.error_alert.rx.pipe(bool),
        )

        self.modal = pn.Modal(pn.Column(self.file_selector, alert))
        self.button = pn.widgets.Button(
            name="Open...",
            icon="folder-open",
            description="Open an existing YAML file...",
            on_click=self.handle_button_click,
        )
        self.confirm_modal = ConfirmModal()

    def handle_button_click(self, event):
        if self.manager.changed:
            self.confirm_modal.show(
                "### ⚠️ **You have unsaved changed**  \n"
                "Opening a new file will discard all unsaved changes.  \n"
                "Do you want to continue?",
                on_confirm=self.modal.show,
                on_cancel=lambda: None,
            )
        else:
            self.modal.show()

    @param.depends("file_list", watch=True)
    def _on_file_selected(self):
        """Triggered on file selection. Loads YAML or sets error alert."""
        if len(self.file_list) != 1:
            self.error_alert = "Only a single YAML file may be loaded at a time"
            return

        self.error_alert = ""
        self.load_yaml(Path(self.file_list[0]))
        # The only way to reset the file selector UI seems to be using a private attr
        self.file_selector._selector.value = []
        self.file_list.clear()

    def load_yaml(self, path):
        """Load waveform configuration from a YAML file.

        Args:
            path: Path object pointing to the YAML file.
        """
        with open(path) as file:
            yaml_content = file.read()

        self.main_gui.plotter_view.plotted_waveforms = {}
        self.main_gui.config.load_yaml(yaml_content)

        if self.main_gui.config.load_error:
            pn.state.notifications.error(
                "YAML could not be loaded:<br>"
                + self.main_gui.config.load_error.replace("\n", "<br>"),
                duration=10000,
            )
            return

        pn.state.notifications.success("Successfully loaded YAML file!")
        self.manager.open_file = path
        self.modal.hide()
        self.main_gui.selector.refresh()
        self.manager.changed = False
