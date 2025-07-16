import panel as pn


class FileSaver:
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def save_yaml(self):
        """Saves the current configuration to the open YAML file."""

        if not self.manager.open_file:
            self.manager.file_creator.modal.show()
            return
        yaml_str = self.manager.main_gui.config.dump()
        with open(self.manager.open_file, "w") as f:
            f.write(yaml_str)
        pn.state.notifications.success("YAML file saved successfully")
