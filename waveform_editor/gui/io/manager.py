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
    is_editing = param.Boolean()

    def __init__(self, main_gui, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.open_file_text = pn.pane.Markdown(width=400)

        self.file_loader = FileLoader(self)
        self.file_creator = FileCreator(self)
        self.file_saver = FileSaver(self)
        file_exporter = FileExporter(self)

        self.panel = pn.Column(
            self.open_file_text,
            pn.Row(
                self.file_creator.button,
                self.file_loader.button,
                self.file_saver.button,
                file_exporter.button,
            ),
            self.file_loader.modal,
            self.file_creator.modal,
            file_exporter.modal,
            visible=self.param.visible,
        )

    @param.depends("is_editing", "open_file", watch=True)
    def set_open_file_text(self):
        if self.open_file:
            self.open_file_text.object = f"**Opened file:**   \n`{self.open_file}`"
        else:
            self.open_file_text.object = "_No file is currently opened_"

    def __panel__(self):
        return self.panel
