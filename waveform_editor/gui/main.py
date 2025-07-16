import logging

import panel as pn
import param

import waveform_editor
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.gui.editor import WaveformEditor
from waveform_editor.gui.io.manager import IOManager
from waveform_editor.gui.plotter_edit import PlotterEdit
from waveform_editor.gui.plotter_view import PlotterView
from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.rename_modal import RenameModal
from waveform_editor.gui.selector.selector import WaveformSelector
from waveform_editor.util import State

logger = logging.getLogger(__name__)


def exception_handler(ex):
    logger.error("Error", exc_info=ex)
    pn.state.notifications.error(f"{ex}")


# Note: these extension() calls take a couple of seconds
# Please avoid importing this module unless actually starting the GUI
pn.extension(
    "modal", "codeeditor", notifications=True, exception_handler=exception_handler
)


class WaveformEditorGui(param.Parameterized):
    VIEW_WAVEFORMS_TAB = 0
    EDIT_WAVEFORMS_TAB = 1

    DISCARD_CHANGES_MESSAGE = (
        "# **⚠️ Warning**  \nYou did not save your changes. "
        "Leaving now will discard any changes you made to this waveform."
        "   \n\n**Are you sure you want to continue?**"
    )

    def __init__(self):
        """Initialize the Waveform Editor Panel App"""
        super().__init__()
        self._reverting_to_editor = State()

        self.config = WaveformConfiguration()

        # Side bar
        self.confirm_modal = ConfirmModal()
        self.rename_modal = RenameModal()
        self.io_manager = IOManager(self)
        self.selector = WaveformSelector(self)
        self.selector.visible = self.io_manager.param.is_editing.rx.bool()
        self.selector.param.watch(self.on_selection_change, "selection")

        sidebar = pn.Column(
            self.io_manager,
            self.selector,
            self.confirm_modal,
            self.rename_modal,
        )

        # Main views: view and edit tabs
        self.editor = WaveformEditor(self.config)
        self.plotter_view = PlotterView()
        self.plotter_edit = PlotterEdit(self.editor)
        self.tabs = pn.Tabs(
            ("View Waveforms", self.plotter_view),
            ("Edit Waveforms", pn.Row(self.editor, self.plotter_edit)),
            dynamic=True,
            visible=self.io_manager.param.is_editing.rx.bool(),
        )
        self.tabs.param.watch(self.on_tab_change, "active")

        # Set multiselect property of the selector based on the active tab:
        allow_multiselect = self.tabs.param.active.rx() == self.VIEW_WAVEFORMS_TAB
        self.selector.multiselect = allow_multiselect

        # Combined UI:
        self.template = pn.template.FastListTemplate(
            title=f"Waveform Editor (v{waveform_editor.__version__})",
            main=self.tabs,
            sidebar=sidebar,
            sidebar_width=400,
        )

    def on_selection_change(self, event):
        """Respond to a changed waveform selection"""
        if self._reverting_to_editor:
            return  # ignore this event when we revert to the editor
        if (
            self.tabs.active == self.EDIT_WAVEFORMS_TAB
            and self.editor.has_changed()
            # Check if current waveform is being removed. The user already confirmed
            # they want to remove the waveform, so we don't ask again:
            and not self.selector.is_removing_waveform
        ):
            self.confirm_modal.show(
                self.DISCARD_CHANGES_MESSAGE,
                on_confirm=self.update_selection,
                on_cancel=self.revert_to_editor,
            )
        else:
            self.update_selection()

    def on_tab_change(self, event):
        """Respond to a tab change"""
        if self._reverting_to_editor:
            return  # ignore this event when we revert to the editor
        if event.old == self.EDIT_WAVEFORMS_TAB and self.editor.has_changed():
            self.confirm_modal.show(
                self.DISCARD_CHANGES_MESSAGE,
                on_confirm=self.update_selection,
                on_cancel=self.revert_to_editor,
            )
        else:
            self.update_selection()

    def update_selection(self):
        """Reflect updated selection in other components"""
        selection = self.selector.selection
        if self.tabs.active == self.EDIT_WAVEFORMS_TAB:
            self.editor.set_waveform(None if not selection else selection[0])
            self.clear_waveform_view()
        elif self.tabs.active == self.VIEW_WAVEFORMS_TAB:
            self.editor.set_waveform(None)
            waveform_map = {name: self.config[name] for name in selection}
            self.plotter_view.plotted_waveforms = waveform_map

    def revert_to_editor(self):
        """Revert to the editor without changing its contents"""
        with self._reverting_to_editor:  # Disable watchers for tab and selection
            self.tabs.active = self.EDIT_WAVEFORMS_TAB
            self.selector.set_selection([self.editor.waveform.name])

    def clear_waveform_view(self):
        self.plotter_view.plotted_waveforms = {}

    def __panel__(self):
        return self.template

    def serve(self):
        """Serve the Panel app"""
        return self.template.servable()


# Run the app
WaveformEditorGui().serve()
