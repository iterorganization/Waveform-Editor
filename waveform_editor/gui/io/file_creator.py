from pathlib import Path

import panel as pn
import param


class YAMLFileCreator(param.Parameterized):
    disabled_description = param.String()
    directory_list = param.List()
    file_name = param.String()
    full_path = param.Path(check_exists=False)

    def __init__(self, file_loader):
        super().__init__()
        self.file_loader = file_loader
        file_selector = pn.widgets.FileSelector.from_param(
            self.param.directory_list,
            file_pattern="",
            directory=Path.cwd(),
            root_directory=Path.cwd().root,
        )
        filename_input = pn.widgets.TextInput.from_param(
            self.param.file_name, placeholder="filename", onkeyup=True, name=""
        )
        confirm_button = pn.widgets.Button(
            name="Create YAML File",
            button_type="primary",
            on_click=self.on_confirm,
            disabled=self.param.disabled_description.rx.pipe(bool),
        )

        self.output_path_text = pn.pane.Markdown(
            visible=self.param.disabled_description.rx.not_()
        )
        modal_content = pn.Column(
            pn.pane.Markdown("# Select directory to store YAML"),
            file_selector,
            pn.pane.Markdown("# Enter filename"),
            pn.Row(filename_input, confirm_button, margin=10),
            self.output_path_text,
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
            description="Create a new YAML file...",
        )
        self._create_button_disabled()

    def on_confirm(self, event):
        self.full_path.touch()
        self.modal.hide()
        self.file_loader.load_yaml(self.full_path)

    @param.depends("disabled_description", watch=True)
    def _set_full_path(self):
        if self.disabled_description:
            self.full_path = None
        else:
            self.full_path = self._create_full_path()
            self.output_path_text.object = (
                f"### Creating new file at:\n `{self.full_path}`"
            )

    @param.depends("directory_list", "file_name", watch=True)
    def _create_button_disabled(self):
        """Determine if the export button is enabled or disabled."""
        message = ""
        if not self.directory_list:
            message = "Provide a directory to store the YAML file into"
        elif len(self.directory_list) != 1:
            message = "Only a single directory must be selected"
        elif not self.file_name:
            message = "Provide a file name"
        elif Path(self.file_name).name != self.file_name:
            message = "File name must not contain path components"
        else:
            full_path = self._create_full_path()
            if full_path.exists():
                message = f"{full_path} already exists!"

        if self.disabled_description != message:
            self.disabled_description = message
        else:
            self.param.trigger("disabled_description")

    def _create_full_path(self):
        file_name_path = Path(self.file_name)
        if file_name_path != ".yaml":
            file_name_path = file_name_path.with_suffix(".yaml")

        return Path(self.directory_list[0]) / file_name_path
