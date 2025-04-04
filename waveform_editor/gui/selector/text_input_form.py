import panel as pn


class TextInputForm:
    """Panel containing a text input field, and a button to accept or cancel the
    current input."""

    def __init__(self, text, is_visible=True, on_click=None):
        self.input = pn.widgets.TextInput(placeholder=text.strip())
        self.button = pn.widgets.ButtonIcon(
            icon="square-rounded-plus",
            size="30px",
            active_icon="square-rounded-plus-filled",
            description="Accept",
            margin=(10, 0, 0, 0),
        )
        if on_click:
            self.button.on_click(on_click)
        self.cancel_button = pn.widgets.ButtonIcon(
            icon="circle-x",
            size="30px",
            active_icon="circle-x-filled",
            description="Cancel",
            margin=(10, 0, 0, 0),
        )
        self.panel = pn.Row(
            self.input,
            self.button,
            self.cancel_button,
            visible=is_visible,
        )
        self.cancel_button.on_click(self._on_select_cancel)

    def is_visible(self, is_visible):
        self.panel.visible = is_visible

    def clear_input(self):
        self.input.value = ""

    def get(self):
        return self.panel

    def _on_select_cancel(self, event):
        self.panel.visible = False
        self.clear_input()
