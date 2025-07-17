from pathlib import Path

import panel as pn
from panel.viewable import Viewer

from waveform_editor.gui.io.filedialog import OpenFileDialog


class FileLoader(Viewer):
    def __init__(self, manager):
        super().__init__()

        self.manager = manager
        self.main_gui = manager.main_gui

        self.file_dialog = OpenFileDialog(Path.cwd().root)
        self.file_dialog.multiselect = False

    def open(self):
        self.file_dialog.open(
            str(Path.cwd()), on_confirm=self._on_file_selected, file_pattern="*.yaml"
        )

    def _on_file_selected(self, file_list):
        """Triggered on file selection. Loads YAML or sets error alert."""
        path = Path(file_list[0])
        self.load_yaml_from_file(path)

    def load_yaml_from_file(self, path):
        """Load waveform configuration from a YAML file.

        Args:
            path: Path object pointing to the YAML file.
        """
        with open(path) as file:
            yaml_content = file.read()

        self.file_dialog.close()
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

    def __panel__(self):
        return self.file_dialog
