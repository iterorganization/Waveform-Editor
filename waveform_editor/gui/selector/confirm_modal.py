import panel as pn


class ConfirmModal:
    """Modal panel containing confirmation message, and options to proceed or cancel
    with the action."""

    def __init__(self, template):
        self.on_confirm = None
        self.on_cancel = None

        self.yes_button = pn.widgets.Button(
            name="Yes", button_type="danger", on_click=self._handle_yes
        )
        self.no_button = pn.widgets.Button(
            name="No", button_type="primary", on_click=self._handle_no
        )
        self.message = pn.pane.Markdown("")
        self.template = template

    def show(self, message, *, on_confirm=None, on_cancel=None):
        self.message.object = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        layout = pn.Column(
            self.message,
            pn.Row(self.yes_button, self.no_button),
        )
        self.template.modal[0].clear()
        self.template.modal[0].append(layout)
        self.template.open_modal()

    def _handle_yes(self, event):
        self.template.close_modal()
        if self.on_confirm:
            self.on_confirm()

    def _handle_no(self, event):
        self.template.close_modal()
        if self.on_cancel:
            self.on_cancel()
