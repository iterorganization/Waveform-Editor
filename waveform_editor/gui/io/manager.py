import panel as pn
import param
from panel.viewable import Viewer

from .file_creator import YAMLFileCreator
from .file_exporter import YAMLFileExporter
from .file_loader import YAMLFileLoader
from .file_saver import YAMLFileSaver


class IOManager(Viewer):
    visible = param.Boolean(default=True, allow_refs=True)
    open_file = param.Path()

    def __init__(self, main_gui, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.open_file_text = pn.pane.Markdown("", visible=True)

        file_loader = YAMLFileLoader(self)
        file_creator = YAMLFileCreator(file_loader)
        file_saver = YAMLFileSaver(self)
        file_exporter = YAMLFileExporter(self)

        self.panel = pn.Column(
            self.open_file_text,
            pn.Row(
                file_creator.button,
                file_loader.button,
                file_saver.button,
                file_exporter.button,
            ),
            file_loader.modal,
            file_creator.modal,
            file_exporter.modal,
            visible=self.param.visible,
        )

    @param.depends("open_file", watch=True)
    def set_open_file_text(self):
        if self.open_file:
            self.open_file_text.object = f"**Opened file:**   \n`{self.open_file}`"
        else:
            self.open_file_text.object = "_No file is currently opened_"

    def __panel__(self):
        return self.panel
