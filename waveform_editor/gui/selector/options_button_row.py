from typing import TYPE_CHECKING

import panel as pn
from panel.viewable import Viewer

from waveform_editor.gui.selector.text_input_form import TextInputForm

if TYPE_CHECKING:
    from waveform_editor.gui.main import WaveformEditorGui
    from waveform_editor.gui.selector.selection_group import SelectionGroup


class OptionsButtonRow(Viewer):
    """Row of options buttons for the SelectionGroup"""

    def __init__(
        self, main_gui: "WaveformEditorGui", selection_group: "SelectionGroup"
    ):
        super().__init__()
        self.main_gui = main_gui
        self.config = main_gui.config
        self.selection_group = selection_group
        self.selector = selection_group.selector
        self.path = selection_group.path
        has_waveforms = selection_group.has_waveforms

        # 'Select all' Button
        self.select_all_button = pn.widgets.ButtonIcon(
            icon="select-all",
            size="20px",
            active_icon="check",
            description="Select all waveforms in this group",
            on_click=selection_group.select_all,
            disabled=self.selector.param.multiselect.rx.not_(),
            visible=has_waveforms,
        )

        # 'Deselect all' Button
        self.deselect_all_button = pn.widgets.ButtonIcon(
            icon="deselect",
            size="20px",
            active_icon="check",
            description="Deselect all waveforms in this group",
            on_click=selection_group.deselect_all,
            visible=has_waveforms,
        )

        # 'Add new waveform' button
        self.new_waveform_button = pn.widgets.ButtonIcon(
            icon="plus",
            size="20px",
            active_icon="check",
            description="Add new waveform",
            on_click=self._on_add_waveform_button_click,
            visible=not self.selection_group.is_root,
        )
        self.new_waveform_panel = TextInputForm(
            "Enter name of new waveform",
            is_visible=False,
            on_click=self._add_new_waveform,
        )

        # 'Remove waveform' button
        self.remove_waveform_button = pn.widgets.ButtonIcon(
            icon="minus",
            size="20px",
            active_icon="check",
            description="Remove selected waveforms in this group",
            on_click=self._show_remove_waveform_modal,
            visible=has_waveforms,
        )

        # 'Add new group' button
        self.new_group_button = pn.widgets.ButtonIcon(
            icon="library-plus",
            size="20px",
            active_icon="check",
            description="Add new group",
            on_click=self._on_add_group_button_click,
        )
        self.new_group_panel = TextInputForm(
            "Enter name of new group",
            is_visible=False,
            on_click=self._add_new_group,
        )

        # 'Remove group' button
        self.remove_group_button = pn.widgets.ButtonIcon(
            icon="trash",
            size="20px",
            active_icon="trash-filled",
            description="Remove this group",
            on_click=self._show_remove_group_modal,
            visible=not self.selection_group.is_root,
        )

        # Combine all into a button row
        option_buttons = pn.Row(
            self.new_waveform_button,
            self.remove_waveform_button,
            self.new_group_button,
            self.select_all_button,
            self.deselect_all_button,
            self.remove_group_button,
        )
        self.panel = pn.Column(
            option_buttons,
            self.new_waveform_panel,
            self.new_group_panel,
        )

    def _show_remove_waveform_modal(self, event):
        if not self.selection_group.get_selection():
            pn.state.notifications.error("No waveforms selected for removal.")
            return
        self.main_gui.modal.show(
            "Are you sure you want to delete the selected waveform(s) from the "
            f"**{self.path[-1]}** group?",
            on_confirm=self._remove_waveforms,
        )

    def _remove_waveforms(self):
        """Remove all selected waveforms in this SelectionGroup."""
        for waveform_name in self.selection_group.get_selection():
            self.config.remove_waveform(waveform_name)
        with self.selector.is_removing_waveform:  # Signal we're removing waveforms
            self.selection_group.sync_waveforms()

    def _show_remove_group_modal(self, event):
        self.main_gui.modal.show(
            f"Are you sure you want to delete the **{self.path[-1]}** group?  \n"
            "This will also remove all waveforms and subgroups in this group!",
            on_confirm=self._remove_group,
        )

    def _remove_group(self):
        """Remove the group."""
        # Remove from config
        self.config.remove_group(self.path)
        # Remove from GUI
        self.selector.remove_group(self.path)

    def _on_add_waveform_button_click(self, event):
        """Show the text input form to add a new waveform."""
        self.new_waveform_panel.is_visible(True)

    def _add_new_waveform(self, event):
        """Add the new waveform to CheckButtonGroup and update the
        WaveformConfiguration."""
        name = self.new_waveform_panel.input.value_input

        # Add empty waveform to YAML
        new_waveform = self.config.parse_waveform(f"{name}:\n- {{}}")
        # TODO: this try-except block can be replaced with a global error handler later
        try:
            self.config.add_waveform(new_waveform, self.path)
        except ValueError as e:
            pn.state.notifications.error(str(e))
            return

        self.selection_group.sync_waveforms()
        self.new_waveform_panel.cancel()

    def _on_add_group_button_click(self, event):
        """Show the text input form to add a new group."""
        self.new_group_panel.is_visible(True)

    def _add_new_group(self, event):
        """Add the new group as a panel accordion and update the YAML."""
        name = self.new_group_panel.input.value_input

        # Create new group in configuration
        try:
            new_group = self.config.add_group(name, self.path)
        except ValueError as e:
            pn.state.notifications.error(str(e))
            return

        # Update UI
        self.selection_group.add_group(new_group)
        self.new_group_panel.cancel()

    def __panel__(self):
        """Returns the panel UI element."""
        return self.panel
