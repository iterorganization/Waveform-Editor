import panel as pn


class RenameModal:
    """Modal panel with for renaming a waveform."""

    def __init__(self, template):
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
        self.template = template

    def show(self, current_name="", *, on_accept=None, on_cancel=None):
        self.input.value = current_name
        self.on_accept = on_accept
        self.on_cancel = on_cancel

        layout = pn.Column(
            self.label,
            self.input,
            pn.Row(self.accept_button, self.cancel_button),
        )

        self.template.modal[0].clear()
        self.template.modal[0].append(layout)
        self.template.open_modal()

    def _handle_accept(self, event):
        self.template.close_modal()
        if self.on_accept:
            self.on_accept(self.input.value)

    def _handle_cancel(self, event):
        self.template.close_modal()
        if self.on_cancel:
            self.on_cancel()
