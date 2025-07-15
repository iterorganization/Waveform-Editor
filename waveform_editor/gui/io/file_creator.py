from pathlib import Path

import panel as pn
import param


class YAMLFileCreator(param.Parameterized):
    disabled_description = param.String()
    directory_list = param.List()
    file_name = param.String()

    def __init__(self):
        super().__init__()
        self.file_selector = pn.widgets.FileSelector.from_param(
            self.param.directory,
            file_pattern="",
            directory=Path.cwd(),
            root_directory=Path.cwd().root,
        )
        self.filename_input = pn.widgets.TextInput.from_param(
            self.param.file_name, placeholder="filename", onkeyup=True, name=""
        )
        confirm_button = pn.widgets.Button(
            name="Confirm",
            button_type="primary",
            on_click=self.on_confirm,
            disabled=self.param.disabled_description.rx.pipe(bool),
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
            "show",
            name="New...",
            icon="file-plus",
        )
        self._export_disabled()

    def on_confirm(self, event):
        file_name_path = Path(self.file_name)
        if file_name_path != ".yaml":
            file_name_path = file_name_path.with_suffix(".yaml")

        full_path = Path(self.directory_list[0]) / file_name_path
        print(full_path)
        self.modal.hide()

    @param.depends("directory", "file_name", watch=True)
    def _export_disabled(self):
        """Determine if the export button is enabled or disabled."""
        message = ""
        if not self.directory_list:
            message = "Please provide a directory to store the YAML file"
        elif len(self.directory_list) != 1:
            message = "Only a single directory must be selected"
        elif not self.file_name:
            message = "Please provide a file name"
        self.disabled_description = message
