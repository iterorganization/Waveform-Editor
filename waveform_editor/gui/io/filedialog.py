import os
from typing import ClassVar

import param
from panel.layout import Modal, Row
from panel.viewable import Viewer
from panel.widgets import Button, TextInput

from waveform_editor.gui.io.filebrowser import FileBrowser


class FileDialogBase(Viewer):
    """Common logic for the Open and Save file dialogs."""

    _cancel_text: ClassVar[str] = "Cancel"
    _confirm_text: ClassVar[str]

    multiselect = param.Boolean(default=True)
    _filename = param.String()

    def __init__(self, root_directory, **params):
        super().__init__(**params)
        self.on_confirm = None
        self.filebrowser = FileBrowser(
            multiselect=self.param.multiselect,
            root_directory=root_directory,
        )
        self.input = TextInput.from_param(
            self.param._filename,
            onkeyup=True,
            name="Filename",
            sizing_mode="stretch_width",
        )
        self.confirm = Button(
            name=self._confirm_text,
            on_click=self._confirm,
            disabled=self.param._filename.rx.not_(),
            align="end",
        )
        self.cancel = Button(
            name=self._cancel_text,
            on_click=self.close,
            align="end",
        )
        self.modal = Modal(
            self.filebrowser,
            Row(self.input, self.confirm, self.cancel),
            open=False,
            show_close_button=False,
            background_close=True,
            width=800,
        )

        self.filebrowser.param.watch(self._on_fileselection_change, "value")
        self.filebrowser.param.watch(self._confirm, "doubleclick")
        self.input.param.watch(self._confirm, "enter_pressed")

    def _on_fileselection_change(self, event):
        if event.new:
            self._filename = ", ".join(os.path.basename(v) for v in event.new)
        else:
            self._filename = ""

    def open(self, directory, fname=None, on_confirm=None, file_pattern="*"):
        """Open the dialog.

        The ``on_confirm`` callback will be called when the user double-clicks a file,
        presses Enter in the text input, or clicks the "Open"/"Save" button. It will
        receive a list of selected file names as only argument. If the callback returns
        True, the dialog will be closed.

        Args:
            directory: Directory to show in the file dialog
            fname: Preselected filename
            on_confirm: Callback when the dialog is confirmed
            file_pattern: A glob-like pattern to filter the files, e.g. *.txt
        """
        self.on_confirm = on_confirm
        self.filebrowser.directory = directory
        self.filebrowser.file_pattern = file_pattern
        self.filebrowser.update()
        self._filename = fname or ""
        self.modal.show()

    def _get_input_fname(self):
        return os.path.join(self.filebrowser.directory, self._filename)

    def _confirm(self, event=None):
        selection = self.filebrowser.value
        if len(selection) == 1 and os.path.isdir(selection[0]):
            self.filebrowser.directory = selection[0]
            self.filebrowser.update()
            return

        if self.on_confirm:
            fnames = selection if self.input.disabled else [self._get_input_fname()]
            if self.on_confirm(fnames):
                self.close()

    def close(self, event=None):
        """Close the dialog."""
        self.modal.hide()

    def __panel__(self):
        return self.modal


class SaveFileDialog(FileDialogBase):
    """A dialog for saving files.

    Example:
        .. code-block:: python

            def on_confirm(fnames):
                if not fnames: return False
                fname = fnames[0]
                with open(fname, "w") as f:
                    f.write(data)
                return True

            dialog = SaveFileDialog("/")
            dialog.open("/path/to/folder", "filename.txt", on_confirm)
    """

    _confirm_text = "Save"

    def __init__(self, root_directory):
        super().__init__(root_directory=root_directory, multiselect=False)


class OpenFileDialog(FileDialogBase):
    """A dialog for opening files.

    Example:
        .. code-block:: python

            def on_confirm(fnames):
                if not fnames: return False
                for fname in fnames:
                    print("Opening file:", fname)
                return True

            dialog = OpenFileDialog("/")
            dialog.open("/path/to/folder", "", on_confirm)
    """

    _confirm_text = "Open"

    def __init__(self, root_directory):
        super().__init__(root_directory=root_directory)
        self.input.disabled = True
