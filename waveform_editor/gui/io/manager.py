import panel as pn
import param
from panel.viewable import Viewer

from .file_exporter import FileExporter
from .file_loader import FileLoader
from .file_saver import FileSaver

NEW = "✏️ New"
OPEN = "📁 Open..."
SAVE = "💾 Save"
SAVE_AS = "💾 Save As..."
EXPORT = "📤 Export..."


class IOManager(Viewer):
    visible = param.Boolean(default=True, allow_refs=True)
    open_file = param.Path()
    is_editing = param.Boolean()
    menu_items = param.List()

    def __init__(self, main_gui, **params):
        self.open_file_text = pn.widgets.StaticText(width=250, align="center")
        self.menu = pn.widgets.MenuButton(name="File", width=120, margin=(15, 10))
        super().__init__(**params)
        self.main_gui = main_gui

        self.file_loader = FileLoader(self)
        self.file_saver = FileSaver(self)
        self.file_exporter = FileExporter(self)

        self.panel = pn.Column(
            pn.Row(self.menu, self.open_file_text),
            pn.Row(  # Ensure the bind doesn't take any UI space
                pn.bind(self._handle_menu_selection, self.menu.param.clicked),
                visible=False,
            ),
            self.file_loader,
            self.file_saver,
            self.file_exporter.modal,
            visible=self.param.visible,
        )

    @param.depends("is_editing", watch=True, on_init=True)
    def _set_menu_items(self):
        if self.is_editing:
            self.menu.items = [NEW, OPEN, SAVE, SAVE_AS, EXPORT]
        else:
            self.menu.items = [NEW, OPEN]

    def create_new_file(self):
        yaml_content = {}
        self.file_loader.load_yaml(yaml_content)
        self.open_file = None

    def _handle_menu_selection(self, clicked):
        if clicked == NEW:
            self.create_new_file()
        elif clicked == OPEN:
            self.file_loader.open()
        elif clicked == SAVE:
            self.file_saver.save_yaml()
        elif clicked == SAVE_AS:
            self.file_saver.open_save_dialog()
        elif clicked == EXPORT:
            self.file_exporter.modal.show()
        # Menu items seem to not retrigger when selecting same twice in a row
        self.menu.clicked = None

    @param.depends("is_editing", "open_file", watch=True, on_init=True)
    def _set_open_file_text(self):
        if not self.is_editing:
            self.open_file_text.value = "Create or open a YAML file"
        elif self.open_file:
            self.open_file_text.value = f"{self.open_file}"
        else:
            self.open_file_text.value = "No file is currently opened"

    def __panel__(self):
        return self.panel
