import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.selection_group import SelectionGroup


class WaveformSelector(Viewer):
    """Panel containing a dynamic waveform selection UI from YAML data."""

    visible = param.Boolean()
    selection = param.List(doc="List of selected waveform names")
    multiselect = param.Boolean(True, doc="Allow selecting multiple waveforms")

    def __init__(self, main_gui):
        super().__init__()
        self.main_gui = main_gui
        self.config = self.main_gui.config
        # FIXME: we should be able to remove this
        self.editor = self.main_gui.editor

        self.confirm_modal = ConfirmModal()
        self.selection_group = SelectionGroup(self, self.config, [])
        self.panel = pn.Column(
            self.selection_group, self.confirm_modal, visible=self.param.visible
        )

        self.prev_selection = []
        self.ignore_tab_watcher = False
        self.ignore_select_watcher = False
        self.warning_message = (
            "# **⚠️ Warning**  \nYou did not save your changes. "
            "Leaving now will discard any changes you made to this waveform."
            "   \n\n**Are you sure you want to continue?**"
        )

    def refresh(self):
        """Discard the current UI state and re-build from self.config.

        Should be called after loading a new configuration.
        """
        self.selection_group = SelectionGroup(self, self.config, [])
        self.panel[0] = self.selection_group
        self.selection = []

    def remove_group(self, path: list[str]):
        """Remove the UI element for the group at the specified path."""
        self.main_gui.editor.stored_string = None  # FIXME: check if we can remove this

        parent_group, group_ui = None, self.selection_group
        for part in path:
            parent_group, group_ui = group_ui, group_ui.selection_groups[part]

        selection_to_delete = group_ui.get_selection(True)
        parent_group.remove_group(path[-1])
        del group_ui
        if selection_to_delete:
            self.selection = [
                val for val in self.selection if val not in selection_to_delete
            ]

    def on_tab_change(self, event):
        """Change selection behavior, depending on which tab is selected."""
        if event.new != self.main_gui.EDIT_WAVEFORMS_TAB and self.editor.has_changed():
            self.confirm_modal.show(
                self.warning_message,
                on_confirm=self.confirm_tab_change,
                on_cancel=self.cancel_tab_change,
            )
            return
        if not self.ignore_tab_watcher:
            self.confirm_tab_change()

    def confirm_tab_change(self):
        if self.main_gui.tabs.active == self.main_gui.EDIT_WAVEFORMS_TAB:
            self.multiselect = False
            # Only keep last selected waveform to edit:
            self.confirm_on_select(self.selection[-1:])
        else:
            self.multiselect = True
            # ensure plot is updated when discarding changes:
            self.main_gui.update_plotted_waveforms(None)

    def cancel_tab_change(self):
        """Revert the selection Select the edit waveforms tab."""
        # Ensure apply_tab_change is not called again through watcher
        self.ignore_tab_watcher = True
        self.main_gui.tabs.active = self.main_gui.EDIT_WAVEFORMS_TAB
        self.ignore_tab_watcher = False

    def on_select(self, event):
        """Handles the selection and deselection of waveforms in the check button
        group.

        Args:
            event: list containing the new selection.
        """
        if self.ignore_select_watcher:
            return

        if self.multiselect:  # Just update all selected
            self.selection = self.selection_group.get_selection(True)

        else:  # Check which one is new and deselect anything else
            new_selection = [name for name in event.new if name not in event.old]
            assert len(new_selection) <= 1

            if self.editor.has_changed():
                self.confirm_modal.show(
                    self.warning_message,
                    on_confirm=lambda: self.confirm_on_select(new_selection),
                    on_cancel=self.cancel_on_select,
                )
            else:
                self.confirm_on_select(new_selection)

    def confirm_on_select(self, new_selection):
        """Only allow for a single waveform to be selected. All waveforms except for
        the newly selected waveform will be deselected.

        Args:
            newly_selected: The newly selected waveform.
        """
        self.ignore_select_watcher = True
        self.selection = new_selection
        self.ignore_select_watcher = False
        # Update editor:
        if new_selection:
            newly_selected_key = new_selection[0]
            # Update code editor with the selected value
            waveform = self.config[newly_selected_key]
            self.editor.set_value(waveform.get_yaml_string())
        else:
            self.editor.set_empty()

    def cancel_on_select(self):
        """Don't change selection"""
        self.ignore_select_watcher = True
        self.param.trigger("selection")
        self.ignore_select_watcher = False

    def __panel__(self):
        """Returns the waveform selector UI component."""
        return self.panel
