from pathlib import Path

import panel as pn


class YAMLFileCreator:
    def __init__(self):
        self.file_selector = pn.widgets.FileSelector(
            file_pattern="",
            directory=Path.cwd(),
            root_directory=Path.cwd().root,
        )
        self.filename_input = pn.widgets.TextInput(placeholder="filename")
        confirm_button = pn.widgets.Button(
            name="Confirm", button_type="primary", on_click=self.on_confirm
        )

        modal_content = pn.Column(
            pn.pane.Markdown("# Select directory to store YAML"),
            self.file_selector,
            pn.pane.Markdown("# Enter filename"),
            pn.Row(self.filename_input, confirm_button, margin=10),
            sizing_mode="stretch_width",
        )

        self.modal = pn.Modal(modal_content)
        self.new_button = self.modal.create_button(
            "show", name="New...", icon="file-plus"
        )

    def on_confirm(self, event):
        print(self.filename_input.value)
        print(self.file_selector.value)
