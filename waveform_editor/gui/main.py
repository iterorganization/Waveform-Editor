import logging
from pathlib import Path

import imas
import panel as pn
import param

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.gui.dict_editor import DictEditor
from waveform_editor.gui.editor import WaveformEditor
from waveform_editor.gui.io.manager import IOManager
from waveform_editor.gui.plotter_edit import PlotterEdit
from waveform_editor.gui.plotter_view import PlotterView
from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.rename_modal import RenameModal
from waveform_editor.gui.selector.selector import WaveformSelector
from waveform_editor.gui.shape_editor.shape_editor import ShapeEditor
from waveform_editor.gui.waveform_content import (
    PLASMA_EDITOR_PAGE,
    WAVEFORM_EDITOR_PAGE,
    WaveformContent,
)
from waveform_editor.util import LATEST_DD_VERSION

logger = logging.getLogger(__name__)
_STYLES_DIR = Path(__file__).parent / "styles"


def exception_handler(ex):
    logger.error("Error", exc_info=ex)
    pn.state.notifications.error(f"{ex}")


# Note: these extension() calls take a couple of seconds
# Please avoid importing this module unless actually starting the GUI
pn.extension(
    "modal",
    "codeeditor",
    "tabulator",
    "terminal",
    "katex",
    notifications=True,
    exception_handler=exception_handler,
)


class WaveformEditorGui(param.Parameterized):
    VIEW_WAVEFORMS_TAB = 0
    EDIT_WAVEFORMS_TAB = 1
    EDIT_YAML_GLOBALS_TAB = 2

    def __init__(self):
        """Initialize the Waveform Editor Panel App"""
        super().__init__()

        self.config = WaveformConfiguration()

        # Side bar
        self.confirm_modal = ConfirmModal()
        self.rename_modal = RenameModal()
        self.io_manager = IOManager(self)
        self.selector = WaveformSelector(self)
        self.selector.param.watch(self.on_selection_change, "selection")

        # Main views: view and edit tabs
        self.editor = WaveformEditor(self.config)
        self.plotter_view = PlotterView()
        self.plotter_edit = PlotterEdit(self.editor)
        globals_editor = pn.Param(
            self.config.globals.param,
            show_name=False,
            widgets={
                "machine_description": {
                    "widget_type": DictEditor,
                    "key_options": imas.IDSFactory(LATEST_DD_VERSION).ids_names(),
                    "names": ("IDS", "URI"),
                }
            },
        )
        shape_editor = ShapeEditor(self)
        self.tabs = pn.Tabs(
            ("View Waveforms", self.plotter_view),
            ("Edit Waveforms", pn.Row(self.editor, self.plotter_edit)),
            ("Edit Global Properties", globals_editor),
            dynamic=True,
        )
        self.tabs.param.watch(self.on_tab_change, "active")

        # Page navigation buttons in the header
        self.nav = pn.widgets.RadioButtonGroup(
            name="Page",
            value=WAVEFORM_EDITOR_PAGE,
            options=[WAVEFORM_EDITOR_PAGE, PLASMA_EDITOR_PAGE],
            button_type="light",
            button_style="outline",
        )
        # Set multiselect property of the selector based on the active tab:
        allow_multiselect = self.tabs.param.active.rx() == self.VIEW_WAVEFORMS_TAB
        self.selector.multiselect = allow_multiselect

        main_content = WaveformContent(
            self.nav,
            self.io_manager,
            self.selector,
            self.confirm_modal,
            self.rename_modal,
            self.tabs,
            shape_editor,
        )

        # Combined UI:
        self.template = pn.template.FastListTemplate(
            header=[self.nav],
            main=[main_content],
            raw_css=[(_STYLES_DIR / "styles.css").read_text()],
        )
        # Disable throttling of busy indicator
        self.template.busy_indicator.throttle = 0

    def on_selection_change(self, _):
        """Respond to a changed waveform selection"""
        self.update_selection()

    def on_tab_change(self, event):
        """Respond to a tab change"""
        entering_edit = event.new == self.EDIT_WAVEFORMS_TAB
        if entering_edit and event.old != self.VIEW_WAVEFORMS_TAB:
            return
        self.update_selection()

    def update_selection(self):
        """Reflect updated selection in other components"""
        selection = self.selector.selection
        if self.tabs.active == self.EDIT_WAVEFORMS_TAB:
            self.editor.set_waveform(None if not selection else selection[0])
            self.plotter_view.plotted_waveforms = {}
        elif self.tabs.active == self.VIEW_WAVEFORMS_TAB:
            self.editor.set_waveform(None)
            waveform_map = {name: self.config[name] for name in selection}
            self.plotter_view.plotted_waveforms = waveform_map

    def load_yaml_from_file(self, path):
        """Load waveform configuration from a YAML file.

        Args:
            path: Path object pointing to the YAML file.
        """
        with open(path) as file:
            yaml_content = file.read()

        self.load_yaml(yaml_content)
        self.io_manager.open_file = path

    def load_yaml(self, yaml_content):
        """Load waveform configuration from YAML string.

        Args:
            yaml_content: YAML string to load.
        """
        self.config.load_yaml(yaml_content)
        if self.config.load_error:
            raise RuntimeError(
                "YAML could not be loaded:<br>"
                + self.config.load_error.replace("\n", "<br>")
            )
        self.nav.value = WAVEFORM_EDITOR_PAGE
        self.tabs.active = self.VIEW_WAVEFORMS_TAB
        self.plotter_view.plotted_waveforms = {}
        self.selector.refresh()

    def __panel__(self):
        return self.template

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Allow serving with `panel serve waveform_editor/gui/main.py`
if "bokeh" in __name__:
    WaveformEditorGui().serve()
