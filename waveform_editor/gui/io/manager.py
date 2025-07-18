from pathlib import Path

import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.gui.io.file_exporter import FileExporter
from waveform_editor.gui.io.file_loader import FileLoader
from waveform_editor.gui.io.file_saver import FileSaver

NEW = "✏️ New"
OPEN = "📁 Open..."
SAVE = "💾 Save"
SAVE_AS = "💾 Save As..."
EXPORT = "📤 Export..."


class IOManager(Viewer):
    visible = param.Boolean(default=True, allow_refs=True)
    open_file = param.ClassSelector(class_=Path)
    config = param.ClassSelector(class_=WaveformConfiguration)
    is_editing = param.Boolean()
    menu_items = param.List()

    def __init__(self, main_gui, **params):
        self.open_file_text = pn.widgets.StaticText(width=250, align="center")
        self.menu = pn.widgets.MenuButton(
            name="File",
            width=120,
            on_click=self._handle_menu_selection,
        )
        self.main_gui = main_gui
        super().__init__(**params)
        self.config = main_gui.config

        self.file_loader = FileLoader(self)
        self.file_saver = FileSaver(self)
        self.file_exporter = FileExporter(self)

        self.panel = pn.Column(
            pn.Row(self.menu, self.open_file_text),
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
        yaml_content = ""
        self.main_gui.load_yaml(yaml_content)
        self.open_file = None

    def _confirm_and_execute(self, action, message):
        def proceed():
            action()

        if self.main_gui.config.has_changed:
            self.main_gui.confirm_modal.show(message, on_confirm=proceed)
        else:
            proceed()

    def _handle_menu_selection(self, event):
        clicked = event.new
        if clicked == NEW:
            self._confirm_and_execute(
                self.create_new_file,
                (
                    "### ⚠️ **You have unsaved changes**  \n"
                    "Opening a new file will discard all unsaved changes.  \n"
                    "Do you want to continue?"
                ),
            )
        elif clicked == OPEN:
            self._confirm_and_execute(
                self.file_loader.open,
                (
                    "### ⚠️ **You have unsaved changes**  \n"
                    "Opening a new file will discard all unsaved changes.  \n"
                    "Do you want to continue?"
                ),
            )
        elif clicked == SAVE:
            self.file_saver.save_yaml()
        elif clicked == SAVE_AS:
            self.file_saver.open_save_dialog()
        elif clicked == EXPORT:
            self._confirm_and_execute(
                self.file_exporter.modal.show,
                (
                    "### ⚠️ **You have unsaved changes**  \n"
                    "Exporting now may not include these unsaved changes.  \n"
                    "Do you want to continue?"
                ),
            )

    @param.depends(
        "is_editing", "open_file", "config.has_changed", watch=True, on_init=True
    )
    def _set_open_file_text(self):
        alert = "⚠️ Unsaved changes " if self.main_gui.config.has_changed else ""
        if not self.is_editing:
            self.open_file_text.value = "Create or open a YAML file"
        elif self.open_file:
            self.open_file_text.value = f"{self.open_file}\n{alert}"
        else:
            self.open_file_text.value = f"Untitled_1.yaml\n{alert}"

    def __panel__(self):
        return self.panel
