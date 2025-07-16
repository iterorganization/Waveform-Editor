from pathlib import Path

import panel as pn
import param


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
        self.button = self.modal.create_button(
            "show",
            name="Open...",
            icon="folder-open",
            description="Open an existing YAML file...",
        )

    @param.depends("file_list", watch=True)
    def _on_file_selected(self):
        """Triggered on file selection. Loads YAML or sets error alert."""
        if len(self.file_list) != 1:
            self.error_alert = "Only a single YAML file may be loaded at a time"
            return

        self.error_alert = ""
        path = Path(self.file_list[0])

        # The only way to reset the file selector UI seems to be using a private attr
        self.file_selector._selector.value = []
        self.file_list.clear()

        self.load_yaml_from_file(path)

    def load_yaml_from_file(self, path):
        """Load waveform configuration from a YAML file.

        Args:
            path: Path object pointing to the YAML file.
        """
        with open(path) as file:
            yaml_content = file.read()

        self.modal.hide()
        self.load_yaml(yaml_content)

        pn.state.notifications.success("Successfully loaded YAML file!")
        self.manager.open_file = path

    def load_yaml(self, yaml_content):
        self.main_gui.config.load_yaml(yaml_content)

        if self.main_gui.config.load_error:
            raise RuntimeError(
                "YAML could not be loaded:<br>"
                + self.main_gui.config.load_error.replace("\n", "<br>")
            )
        self.main_gui.clear_waveform_view()
        self.manager.is_editing = True
        self.main_gui.selector.refresh()
