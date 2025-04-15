import panel as pn
import param
from panel.viewable import Viewer


class StartUpPrompt(Viewer):
    """Panel containing a start-up prompt for loading YAML or starting from a new
    yaml file."""

    visible = param.Boolean(
        default=True,
        doc="The visibility of the start-up prompt.",
    )

    def __init__(self, main_gui):
        super().__init__()
        self.main_gui = main_gui
        self.file_input = pn.widgets.FileInput(accept=".yaml")
        self.file_input.param.watch(self.main_gui.load_yaml, "value")

        self.sidebar_text = pn.pane.Markdown(
            "## Select Waveform Editor YAML File", margin=0
        )

        self.new_yaml_text = pn.pane.Markdown("## Or\n")
        self.new_yaml_button = pn.widgets.Button(
            name="Create a new YAML file",
            button_type="primary",
            on_click=self._start_new,
        )
        self.panel = pn.Column(
            self.sidebar_text,
            self.file_input,
            self.new_yaml_text,
            self.new_yaml_button,
        )
        self.param.watch(self.is_visible, "visible")

    def _start_new(self, event):
        """Sets up the GUI to start from a new, empty yaml."""
        self.is_visible(False)
        self.main_gui.file_download.filename = "new.yaml"
        self.main_gui.make_ui_visible(True)
        self.main_gui.selector.create_waveform_selector_ui()

    def is_visible(self, event):
        """Sets visibility of the start-up prompt."""
        self.sidebar_text.visible = self.visible
        self.file_input.visible = self.visible
        self.new_yaml_text.visible = self.visible
        self.new_yaml_button.visible = self.visible

    def __panel__(self):
        return self.panel
