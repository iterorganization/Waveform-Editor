from pathlib import Path

import panel as pn
import param


class YAMLFileCreator(param.Parameterized):
    disabled_description = param.String()
    directory_list = param.List()
    file_name = param.String()

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.file_selector = pn.widgets.FileSelector.from_param(
            self.param.directory_list,
            file_pattern="",
            directory=Path.cwd(),
            root_directory=Path.cwd().root,
        )
        self.filename_input = pn.widgets.TextInput.from_param(
            self.param.file_name, placeholder="filename", onkeyup=True, name=""
        )
        confirm_button = pn.widgets.Button(
            name="Create YAML File",
            button_type="primary",
            on_click=self.on_confirm,
            disabled=self.param.disabled_description.rx.pipe(bool),
        )

        modal_content = pn.Column(
            pn.pane.Markdown("# Select directory to store YAML"),
            self.file_selector,
            pn.pane.Markdown("# Enter filename"),
            pn.Row(self.filename_input, confirm_button, margin=10),
            pn.pane.Alert(
                self.param.disabled_description,
                visible=self.param.disabled_description.rx.pipe(bool),
                alert_type="warning",
            ),
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
        if full_path.exists():
            pn.state.notifications.error(f"{full_path} already exists!")
            return

        full_path.touch()
        self.modal.hide()
        self.controller.file_loader.load_yaml(full_path)

    @param.depends("directory_list", "file_name", watch=True)
    def _export_disabled(self):
        """Determine if the export button is enabled or disabled."""
        message = ""
        if not self.directory_list:
            message = "Provide a directory to store the YAML file into"
        elif len(self.directory_list) != 1:
            message = "Only a single directory must be selected"
        elif not self.file_name:
            message = "Provide a file name"
        self.disabled_description = message
