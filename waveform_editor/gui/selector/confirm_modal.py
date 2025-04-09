import panel as pn
from panel.viewable import Viewer


class ConfirmModal(Viewer):
    """Modal panel containing confirmation message, and options to proceed or cancel
    with the action."""

    def __init__(self):
        self.on_confirm = None
        self.on_cancel = None

        self.yes_button = pn.widgets.Button(
            name="Yes", button_type="danger", on_click=self._handle_yes
        )
        self.no_button = pn.widgets.Button(
            name="No", button_type="primary", on_click=self._handle_no
        )
        self.message = pn.pane.Markdown("")

        content = pn.Column(
            self.message,
            pn.Row(self.yes_button, self.no_button),
        )

        self.modal = pn.Modal(
            content, open=False, show_close_button=False, background_close=False
        )

    def show(self, message, *, on_confirm=None, on_cancel=None):
        self.message.object = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.modal.show()

    def _handle_yes(self, event):
        self.modal.hide()
        if self.on_confirm:
            self.on_confirm()

    def _handle_no(self, event):
        self.modal.hide()
        if self.on_cancel:
            self.on_cancel()

    def __panel__(self):
        return self.modal
