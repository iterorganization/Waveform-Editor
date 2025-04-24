import panel as pn
from panel.viewable import Viewer

from waveform_editor.gui.selector.text_input_form import TextInputForm


class OptionsButtonRow(Viewer):
    def __init__(self, main_gui, check_buttons, path):
        self.main_gui = main_gui
        self.parent_ui = None
        self.parent_accordion = None
        self.check_buttons = check_buttons
        self.path = path

        # 'Select all' Button
        self.select_all_button = pn.widgets.ButtonIcon(
            icon="select-all",
            size="20px",
            active_icon="check",
            description="Select all waveforms in this group",
            on_click=self._select_all,
        )

        # 'Deselect all' Button
        self.deselect_all_button = pn.widgets.ButtonIcon(
            icon="deselect",
            size="20px",
            active_icon="check",
            description="Deselect all waveforms in this group",
            on_click=self._deselect_all,
        )

        # 'Add new waveform' button
        self.new_waveform_button = pn.widgets.ButtonIcon(
            icon="plus",
            size="20px",
            active_icon="check",
            description="Add new waveform",
            on_click=self._on_add_waveform_button_click,
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
            option_buttons, self.new_waveform_panel, self.new_group_panel
        )

        if not self.check_buttons.options:
            self._show_filled_options(False)

    def _show_filled_options(self, show_options):
        """Whether to show the selection and waveform removal button.

        Args:
            show_options: flag to show options.
        """
        self.select_all_button.visible = show_options
        self.remove_waveform_button.visible = show_options
        self.deselect_all_button.visible = show_options

    def _show_remove_waveform_modal(self, event):
        if not self.check_buttons.value:
            pn.state.notifications.error("No waveforms selected for removal.")
            return
        self.main_gui.modal.show(
            "Are you sure you want to delete the selected waveform(s) from the "
            f"**{self.parent_ui.name}** group?",
            on_confirm=self._remove_waveforms,
        )

    def _remove_waveforms(self):
        """Remove all selected waveforms in this CheckButtonGroup."""
        selected_waveforms = self.check_buttons.value.copy()
        for waveform_name in selected_waveforms:
            self.main_gui.selector.config.remove_waveform(waveform_name)
            self.check_buttons.options.remove(waveform_name)
        self.check_buttons.value = []
        self.check_buttons.param.trigger("options")
        self.main_gui.plotter.param.trigger("plotted_waveforms")

        # Remove options if there are no waveforms
        if len(self.check_buttons.options) == 0:
            self._show_filled_options(False)

    def _show_remove_group_modal(self, event):
        self.main_gui.modal.show(
            "Are you sure you want to delete the selected waveform(s) from the "
            f"**{self.parent_ui.name}** group?",
            on_confirm=self._remove_group,
        )

    def _remove_group(self):
        """Remove the group."""

        # TODO: This prevents deleted waveforms from remaining in the plotter.
        # It would be nicer to have the selected waveforms which are not in the deleted
        # group to stay selected.
        self.main_gui.selector.deselect_all()
        self.main_gui.selector.config.remove_group(self.path)

        # Remove group from UI
        for idx, column in enumerate(self.parent_accordion):
            if self.path[-1] == column.name:
                self.parent_accordion.pop(idx)
                break
        self.main_gui.plotter.param.trigger("plotted_waveforms")

    def _deselect_all(self, event):
        """Deselect all waveforms in this CheckButtonGroup."""
        self.check_buttons.value = []

    def _select_all(self, event):
        """Select all waveforms in this CheckButtonGroup."""
        # Convert to list to ensure the check_button.value watcher is triggered
        self.check_buttons.value = list(self.check_buttons.options)

    def _on_add_waveform_button_click(self, event):
        """Show the text input form to add a new waveform."""
        self.new_waveform_panel.is_visible(True)

    def _add_new_waveform(self, event):
        """Add the new waveform to CheckButtonGroup and update the
        WaveformConfiguration."""
        name = self.new_waveform_panel.input.value

        # Add empty waveform to YAML
        new_waveform = self.main_gui.config.parse_waveform(f"{name}: [{{}}]")
        # TODO:this try-except block can be replaced with a global error handler later
        try:
            self.main_gui.selector.config.add_waveform(new_waveform, self.path)
        except ValueError as e:
            pn.state.notifications.error(str(e))
            return

        self.check_buttons.options.append(name)
        self.check_buttons.param.trigger("options")

        self._show_filled_options(True)
        self.new_waveform_panel.is_visible(False)
        self.new_waveform_panel.clear_input()

    def _on_add_group_button_click(self, event):
        """Show the text input form to add a new group."""
        self.new_group_panel.is_visible(True)

    def _add_new_group(self, event):
        """Add the new group as a panel accordion and update the YAML."""
        name = self.new_group_panel.input.value
        if name == "":
            pn.state.notifications.error("Group name may not be empty.")
            return

        if "/" in name:
            pn.state.notifications.error("Groups may not contain '/'.")
            return

        # Create new group in configuration
        try:
            new_group = self.main_gui.selector.config.add_group(name, self.path)
        except ValueError:
            pn.state.notifications.error(f"{name!r} already exists in current group.")
            return

        new_path = self.path + [name]

        # Check if there exists an accordion already at this level
        existing_accordion = None
        for obj in self.parent_ui.objects:
            if isinstance(obj, pn.Accordion):
                existing_accordion = obj
                break

        if not existing_accordion:
            new_accordion = pn.Accordion()

        parent_accordion = existing_accordion if existing_accordion else new_accordion
        new_group_ui = self.main_gui.selector.create_group_ui(
            new_group, new_path, parent_accordion=parent_accordion
        )
        # Update UI with new group
        if existing_accordion:
            if name in existing_accordion._names:
                pn.state.notifications.error(f"A group named '{name}' already exists.")
                return

            existing_accordion.append((name, new_group_ui))
        else:
            new_accordion.objects = [new_group_ui]
            self.parent_ui.append(new_accordion)

        self.new_group_panel.is_visible(False)
        self.new_group_panel.clear_input()

    def __panel__(self):
        """Returns the panel UI element."""
        return self.panel
