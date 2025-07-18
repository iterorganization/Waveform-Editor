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
        self.file_dialog.close()
        self.main_gui.load_yaml_from_file(path)
        pn.state.notifications.success("Successfully loaded YAML file!")

    def __panel__(self):
        return self.file_dialog
