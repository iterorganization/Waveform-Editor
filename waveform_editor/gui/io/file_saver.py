from pathlib import Path

import panel as pn
from panel.viewable import Viewer

from waveform_editor.gui.io.filedialog import SaveFileDialog


class FileSaver(Viewer):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.file_dialog = SaveFileDialog(Path.cwd().root)

    def save_yaml(self):
        """Saves the current configuration to the open YAML file."""

        if not self.manager.open_file:
            self.open_save_dialog()
            return
        yaml_str = self.manager.main_gui.config.dump()
        with open(self.manager.open_file, "w") as f:
            f.write(yaml_str)
        pn.state.notifications.success("YAML file saved successfully")
        self.manager.main_gui.config.has_changed = False

    def open_save_dialog(self):
        start_path = Path.cwd()
        file_name = None
        if self.manager.open_file:
            start_path = self.manager.open_file.parent
            file_name = self.manager.open_file.name
        self.file_dialog.open(
            str(start_path),
            on_confirm=self.on_confirm,
            file_pattern="*.yaml",
            fname=file_name,
        )

    def on_confirm(self, file_list):
        """Creates a new empty YAML file and loads it."""
        path = Path(file_list[0])

        if path.suffix == ".yml":
            path = path.with_suffix(".yaml")
        elif path.suffix != ".yaml":
            path = path.with_suffix(path.suffix + ".yaml")

        def proceed():
            self.manager.open_file = path
            self.file_dialog.close()
            self.save_yaml()

        if path.exists():
            self.manager.main_gui.confirm_modal.show(
                f"File '{path.name}' already exists.  \n Do you want to overwrite it?",
                on_confirm=proceed,
            )
        else:
            # Ensure the file exists before saving YAML
            path.touch()
            proceed()

    def __panel__(self):
        return self.file_dialog
