from pathlib import Path

import panel as pn


class YAMLFileLoader:
    def __init__(self, main_gui):
        self.main_gui = main_gui
        self.open_file = None

        self.open_file_text = pn.pane.Markdown("", visible=False)
        self.open_file_selector = pn.widgets.FileSelector(
            directory=Path.cwd(),
            root_directory=Path.cwd().root,
            file_pattern="*.yaml",
            only_files=True,
        )
        self.open_file_selector.param.watch(self.load_yaml, "value")
        self.modal = pn.Modal(self.open_file_selector)
        self.open_button = self.modal.create_button(
            "show", name="Open...", icon="folder-open"
        )

    def load_yaml(self, event):
        if len(self.open_file_selector.value) != 1:
            pn.state.notifications.error(
                "Only a single YAML file may be loaded at a time"
            )
            return

        with open(self.open_file_selector.value[0]) as file:
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
        self.open_file = Path(self.open_file_selector.value[0])
        self.open_file_text.object = f"**Opened file:** `{self.open_file}`"
        self.open_file_text.visible = True
        self.modal.hide()
        self.main_gui.selector.refresh()
