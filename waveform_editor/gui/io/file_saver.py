import panel as pn


class FileSaver:
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.button = pn.widgets.Button(
            name="Save",
            icon="device-floppy",
            description="Save the YAML file",
            on_click=lambda event: self.save_yaml(),
            visible=self.manager.param.open_file.rx.bool(),
        )

    def save_yaml(self):
        """Saves the current configuration to the open YAML file."""

        if not self.manager.open_file:
            pn.state.notifications.error("No YAML file is currently opened")
            return
        yaml_str = self.manager.main_gui.config.dump()
        with open(self.manager.open_file, "w") as f:
            f.write(yaml_str)
        pn.state.notifications.success("YAML file saved successfully")
