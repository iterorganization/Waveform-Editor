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
    menu_items = param.List()

    def __init__(self, main_gui, **params):
        self.open_file_text = pn.widgets.StaticText(align="center")
        self.menu = pn.widgets.MenuButton(
            name="File",
            width=120,
            on_click=self._handle_menu_selection,
            items=[NEW, OPEN, SAVE, SAVE_AS, EXPORT],
        )
        self.open_file_tool_tip = pn.widgets.TooltipIcon()
        self.main_gui = main_gui
        super().__init__(**params)

        self.config = main_gui.config
        self.open_file_tool_tip.visible = (
            self.open_file_tool_tip.param.value.rx.bool()
            or self.main_gui.config.param.has_changed.rx.bool()
        )
        self.file_loader = FileLoader(self)
        self.file_saver = FileSaver(self)
        self.file_exporter = FileExporter(self)

        self.panel = pn.Column(
            pn.Row(self.menu, self.open_file_text, self.open_file_tool_tip),
            self.file_loader,
            self.file_saver,
            self.file_exporter.modal,
            visible=self.param.visible,
        )

    def create_new_file(self):
        yaml_content = ""
        self.main_gui.load_yaml(yaml_content)
        self.open_file = None

    def _confirm_unsaved_changes(self, action, message):
        if self.main_gui.config.has_changed or self.main_gui.editor.has_changed():
            message = f"""\
            ### ⚠️ **You have unsaved changes**
            {message}  
            Do you want to continue?"""
            self.main_gui.confirm_modal.show(message, on_confirm=action)
        else:
            action()

    def _handle_menu_selection(self, event):
        clicked = event.new
        if clicked == NEW:
            self._confirm_unsaved_changes(
                self.create_new_file,
                "Creating a new file will discard all unsaved changes.",
            )
        elif clicked == OPEN:
            self._confirm_unsaved_changes(
                self.file_loader.open,
                "Opening another file will discard all unsaved changes.",
            )
        elif clicked == SAVE:
            self.file_saver.save_yaml()
        elif clicked == SAVE_AS:
            self.file_saver.open_save_dialog()
        elif clicked == EXPORT:
            self._confirm_unsaved_changes(
                self.file_exporter.modal.show,
                "Exporting now may not include these unsaved changes.",
            )

    @param.depends("open_file", "config.has_changed", watch=True, on_init=True)
    def _set_open_file_text(self):
        unsaved_icon = "*" if self.main_gui.config.has_changed else ""
        tooltip_msg = (
            "There are unsaved changes." if self.main_gui.config.has_changed else ""
        )
        if self.open_file:
            self.open_file_text.value = f"{unsaved_icon}{self.open_file.name}"
            self.open_file_tool_tip.value = (
                f"**Full path:** `{self.open_file}`  \n{tooltip_msg}"
            )
        else:
            self.open_file_text.value = f"{unsaved_icon}Untitled_1.yaml"
            self.open_file_tool_tip.value = tooltip_msg

    def __panel__(self):
        return self.panel
