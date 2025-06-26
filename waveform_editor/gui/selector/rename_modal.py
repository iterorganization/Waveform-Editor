import panel as pn
from panel.viewable import Viewer


class RenameModal(Viewer):
    """Modal panel with for renaming a waveform."""

    def __init__(self):
        self.on_accept = None
        self.on_cancel = None

        self.label = pn.pane.Markdown("**Enter a new name for the waveform:**")
        self.input = pn.widgets.TextInput(placeholder="Enter new name")
        self.accept_button = pn.widgets.Button(
            name="Accept", button_type="primary", on_click=self._handle_accept
        )
        self.cancel_button = pn.widgets.Button(
            name="Cancel", button_type="default", on_click=self._handle_cancel
        )

        content = pn.Column(
            self.label,
            self.input,
            pn.Row(self.accept_button, self.cancel_button),
        )

        self.modal = pn.Modal(
            content, open=False, show_close_button=False, background_close=False
        )

    def show(self, current_name="", *, on_accept=None, on_cancel=None):
        self.input.value = current_name
        self.on_accept = on_accept
        self.on_cancel = on_cancel
        self.modal.show()

    def _handle_accept(self, event):
        self.modal.hide()
        if self.on_accept:
            self.on_accept(self.input.value)

    def _handle_cancel(self, event):
        self.modal.hide()
        if self.on_cancel:
            self.on_cancel()

    def __panel__(self):
        return self.modal
