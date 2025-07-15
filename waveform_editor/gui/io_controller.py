from pathlib import Path

import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.export_dialog import ExportDialog


class IOController(Viewer):
    visible = param.Boolean(
        default=True,
        doc="The visibility of the start-up prompt.",
        allow_refs=True,
    )

    def __init__(self, main_gui, visible=True, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.visible = visible
        self.open_file = None

        self.open_file_text = pn.pane.Markdown("", visible=False)

        self.file_selector = pn.widgets.FileSelector(
            directory=Path.cwd(),
            root_directory=Path.cwd().root,
            file_pattern="*.yaml",
            only_files=True,
            show_hidden=False,
        )
        self.file_selector.param.watch(self.load_yaml, "value")
        self.modal = pn.Modal(
            self.file_selector,
            open=False,
        )

        export_dialog = ExportDialog(self.main_gui)
        self.export_button = pn.widgets.Button(
            name="Export", icon="upload", on_click=export_dialog.open
        )
        self.new_button = pn.widgets.Button(
            name="New...",
            icon="file-plus",
        )
        self.open_button = pn.widgets.Button(
            name="Open...", icon="folder-open", on_click=lambda event: self.modal.show()
        )
        self.save_button = pn.widgets.Button(
            name="Save",
            icon="device-floppy",
            on_click=lambda event: self.save_yaml(),
        )

        self.panel = pn.Column(
            self.open_file_text,
            pn.Row(
                self.new_button, self.open_button, self.save_button, self.export_button
            ),
            self.modal,
            export_dialog,
            visible=self.param.visible,
        )

    def load_yaml(self, event):
        """Load waveform configuration from a YAML file.

        Args:
            event: The event object containing the uploaded file data.
        """
        if len(self.file_selector.value) != 1:
            pn.state.notifications.error(
                "Only a single YAML file may be loaded at a time"
            )
            return

        with open(self.file_selector.value[0]) as file:
            yaml_content = file.read()
        self.main_gui.plotter_view.plotted_waveforms = {}
        self.main_gui.config.load_yaml(yaml_content)

        if self.main_gui.config.load_error:
            pn.state.notifications.error(
                "YAML could not be loaded:<br>"
                + self.main_gui.config.load_error.replace("\n", "<br>"),
                duration=10000,
            )
            self.show_startup_options = True
            return

        pn.state.notifications.success("Successfully loaded YAML file!")
        self.open_file = Path(self.file_selector.value[0])
        self.open_file_text.object = f"**Opened file:** `{self.open_file}`"
        self.open_file_text.visible = True
        self.show_startup_options = False
        self.modal.hide()

        # Create tree structure in sidebar based on waveform groups in YAML
        self.main_gui.selector.refresh()

    def save_yaml(self):
        if not self.open_file:
            pn.state.notifications.error("No YAML file is currently opened")
            return
        yaml_str = self.main_gui.config.dump()
        with open(self.open_file, "w") as f:
            f.write(yaml_str)
        pn.state.notifications.success("YAML file saved successfully")

    def __panel__(self):
        return self.panel
