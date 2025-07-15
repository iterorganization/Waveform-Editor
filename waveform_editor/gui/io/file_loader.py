from pathlib import Path

import panel as pn
import param


class YAMLFileLoader(param.Parameterized):
    def __init__(self, controller):
        super().__init__()

        self.controller = controller
        self.main_gui = controller.main_gui

        self.file_selector = pn.widgets.FileSelector(
            directory=Path.cwd(),
            root_directory=Path.cwd().root,
            file_pattern="*.yaml",
            only_files=True,
        )
        self.file_selector.param.watch(self._on_file_selected, "value")
        self.modal = pn.Modal(self.file_selector)
        self.open_button = self.modal.create_button(
            "show",
            name="Open...",
            icon="folder-open",
            description="Open an existing YAML file...",
        )

    def _on_file_selected(self, event):
        if len(self.file_selector.value) != 1:
            pn.state.notifications.error(
                "Only a single YAML file may be loaded at a time"
            )
            return

        self.load_yaml(Path(self.file_selector.value[0]))

    def load_yaml(self, path):
        with open(path) as file:
            yaml_content = file.read()

        self.main_gui.plotter_view.plotted_waveforms = {}
        self.main_gui.config.load_yaml(yaml_content)

        if self.main_gui.config.load_error:
            pn.state.notifications.error(
                "YAML could not be loaded:<br>"
                + self.main_gui.config.load_error.replace("\n", "<br>"),
                duration=10000,
            )
            return

        pn.state.notifications.success("Successfully loaded YAML file!")
        self.controller.open_file = path
        self.modal.hide()
        self.main_gui.selector.refresh()
