import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.export_dialog import ExportDialog

from .file_creator import YAMLFileCreator
from .file_loader import YAMLFileLoader


class FileManager(Viewer):
    visible = param.Boolean(default=True, allow_refs=True)

    def __init__(self, main_gui, visible=True, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.visible = visible

        self.open_controller = YAMLFileLoader(main_gui)
        self.new_controller = YAMLFileCreator()

        export_dialog = ExportDialog(self.main_gui)
        self.export_button = pn.widgets.Button(
            name="Export", icon="upload", on_click=export_dialog.open
        )
        self.save_button = pn.widgets.Button(
            name="Save",
            icon="device-floppy",
            on_click=lambda event: self.save_yaml(),
        )

        self.panel = pn.Column(
            self.open_controller.open_file_text,
            pn.Row(
                self.new_controller.new_button,
                self.open_controller.open_button,
                self.save_button,
                self.export_button,
            ),
            self.open_controller.modal,
            self.new_controller.modal,
            export_dialog,
            visible=self.param.visible,
        )

    def save_yaml(self):
        if not self.open_controller.open_file:
            pn.state.notifications.error("No YAML file is currently opened")
            return
        yaml_str = self.main_gui.config.dump()
        with open(self.open_controller.open_file, "w") as f:
            f.write(yaml_str)
        pn.state.notifications.success("YAML file saved successfully")

    def __panel__(self):
        return self.panel
