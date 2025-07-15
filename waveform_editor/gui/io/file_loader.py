from pathlib import Path

import panel as pn
import param


class FileLoader(param.Parameterized):
    file_list = param.MultiFileSelector()
    error_alert = param.String()

    def __init__(self, controller):
        super().__init__()

        self.controller = controller
        self.main_gui = controller.main_gui

        file_selector = pn.widgets.FileSelector.from_param(
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

        self.modal = pn.Modal(pn.Column(file_selector, alert))
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
        self.load_yaml(Path(self.file_list[0]))

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
        self.controller.open_file = path
        self.modal.hide()
        self.main_gui.selector.refresh()
