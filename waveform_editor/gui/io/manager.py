import panel as pn
import param
from panel.viewable import Viewer

from .export_dialog import ExportDialog
from .file_creator import YAMLFileCreator
from .file_loader import YAMLFileLoader


class IOManager(Viewer):
    visible = param.Boolean(default=True, allow_refs=True)
    open_file = param.Path()

    def __init__(self, main_gui, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.open_file_text = pn.pane.Markdown("", visible=True)
        file_loader = YAMLFileLoader(self)
        file_creator = YAMLFileCreator(file_loader)

        export_dialog = ExportDialog(self.main_gui)
        export_button = pn.widgets.Button(
            name="Export",
            icon="upload",
            description="Export the YAML file",
            on_click=export_dialog.open,
            visible=self.param.open_file.rx.bool(),
        )
        save_button = pn.widgets.Button(
            name="Save",
            icon="device-floppy",
            description="Save the YAML file",
            on_click=lambda event: self.save_yaml(),
            visible=self.param.open_file.rx.bool(),
        )

        self.panel = pn.Column(
            self.open_file_text,
            pn.Row(
                file_creator.new_button,
                file_loader.open_button,
                save_button,
                export_button,
            ),
            file_loader.modal,
            file_creator.modal,
            export_dialog,
            visible=self.param.visible,
        )

    @param.depends("open_file", watch=True)
    def set_open_file_text(self):
        if self.open_file:
            self.open_file_text.object = f"**Opened file:**   \n`{self.open_file}`"
        else:
            self.open_file_text.object = "_No file is currently opened_"

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
