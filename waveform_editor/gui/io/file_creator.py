import param


class FileCreator(param.Parameterized):
    disabled_description = param.String()
    directory_list = param.List()
    file_name = param.String()
    full_path = param.Path(check_exists=False)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def create_new_file(self):
        yaml_content = {}
        self.manager.file_loader.load_yaml(yaml_content)
        self.manager.open_file = None
