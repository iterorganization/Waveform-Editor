import panel as pn
import param
from panel.viewable import Viewer

from .file_creator import FileCreator
from .file_exporter import FileExporter
from .file_loader import FileLoader
from .file_saver import FileSaver


class IOManager(Viewer):
    visible = param.Boolean(default=True, allow_refs=True)
    open_file = param.Path()
    changed = param.Boolean()

    def __init__(self, main_gui, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.open_file_text = pn.pane.Markdown(width=400)

        self.file_loader = FileLoader(self)
        file_creator = FileCreator(self)
        file_saver = FileSaver(self)
        file_exporter = FileExporter(self)

        self.panel = pn.Column(
            self.open_file_text,
            pn.Row(
                file_creator.button,
                self.file_loader.button,
                file_saver.button,
                file_exporter.button,
            ),
            self.file_loader.modal,
            file_creator.modal,
            file_exporter.modal,
            self.file_loader.confirm_modal,
            file_creator.confirm_modal,
            file_exporter.confirm_modal,
            visible=self.param.visible,
        )

    @param.depends("open_file", "changed", watch=True)
    def set_open_file_text(self):
        if self.open_file:
            alert = "⚠️ Unsaved changes " if self.changed else ""
            self.open_file_text.object = (
                f"**Opened file:** {alert}   \n`{self.open_file}`"
            )
        else:
            self.open_file_text.object = "_No file is currently opened_"

    def __panel__(self):
        return self.panel
