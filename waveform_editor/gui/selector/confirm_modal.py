import panel as pn
from panel.viewable import Viewer
from panel_modal import Modal


class ConfirmModal(Viewer):
    def __init__(self, message, on_confirm=None, on_cancel=None):
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        self.yes_button = pn.widgets.Button(
            name="Yes", button_type="danger", on_click=self._handle_yes
        )
        self.no_button = pn.widgets.Button(
            name="No", button_type="primary", on_click=self._handle_no
        )

        # Modal content
        content = pn.Column(
            pn.pane.Markdown(self.message),
            pn.Row(self.yes_button, self.no_button),
        )

        self.modal = Modal(
            content,
            open=False,
            show_close_button=False,
        )

    def open(self):
        self.modal.open = True

    def close(self):
        self.modal.close = True

    def _handle_yes(self, event):
        if self.on_confirm:
            self.on_confirm()
        self.close()

    def _handle_no(self, event):
        if self.on_cancel:
            self.on_cancel()
        self.close()

    def __panel__(self):
        return self.modal
