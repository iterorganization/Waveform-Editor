import panel as pn
from panel_modal import Modal


class ConfirmModal:
    def __init__(self, message, width=400, on_confirm=None, on_cancel=None):
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        self.yes_button = pn.widgets.Button(
            name="Yes", button_type="danger", width=100, on_click=self._handle_yes
        )
        self.no_button = pn.widgets.Button(
            name="No", button_type="primary", width=100, on_click=self._handle_no
        )

        # Modal content
        content = pn.Column(
            pn.pane.Markdown(self.message),
            pn.Row(self.yes_button, self.no_button),
            sizing_mode="stretch_width",
        )

        self.modal = Modal(
            content,
            name="Confirm Action",
            open=False,
            width=width,
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

    def get(self):
        return self.modal
