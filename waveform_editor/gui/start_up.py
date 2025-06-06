import panel as pn
import param
from panel.viewable import Viewer


class StartUpPrompt(Viewer):
    """Panel containing a start-up prompt for loading YAML or starting from a new
    YAML file."""

    visible = param.Boolean(
        default=True,
        doc="The visibility of the start-up prompt.",
        allow_refs=True,
    )

    def __init__(self, main_gui, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.file_input = pn.widgets.FileInput(accept=".yaml")
        self.file_input.param.watch(self.main_gui.load_yaml, "value")

        self.selection_text = pn.pane.Markdown(
            "## Select Waveform Editor YAML File", margin=0
        )

        self.or_text = pn.pane.Markdown("## Or")
        self.create_new_yaml_button = pn.widgets.Button(
            name="Create a new YAML file",
            button_type="primary",
            on_click=self._create_new,
        )
        self.panel = pn.Column(
            self.selection_text,
            self.file_input,
            self.or_text,
            self.create_new_yaml_button,
            visible=self.param.visible,
        )

    def _create_new(self, event):
        """Sets up the GUI to start from a new, empty yaml."""
        self.visible = False
        self.main_gui.file_download.filename = "new.yaml"
        self.main_gui.show_startup_options = False
        self.main_gui.selector.refresh()

    def __panel__(self):
        return self.panel
