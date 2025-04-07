import panel as pn
from panel.viewable import Viewer

from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.text_input_form import TextInputForm
from waveform_editor.yaml_parser import YamlParser


class OptionsButtonRow(Viewer):
    def __init__(self, selector, check_buttons, path):
        self.selector = selector
        self.parent_ui = None
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
        self.remove_waveform_modal = ConfirmModal(
            message="Are you sure you want to delete the selected waveform(s)?",
            on_confirm=self._remove_waveforms,
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

        # Combine all into a button row
        option_buttons = pn.Row(
            self.new_waveform_button,
            self.remove_waveform_button,
            self.new_group_button,
            self.select_all_button,
            self.deselect_all_button,
        )
        self.panel = pn.Column(
            option_buttons,
            self.new_waveform_panel,
            self.new_group_panel,
            self.remove_waveform_modal,
        )

        if not self.check_buttons.options:
            self.select_all_button.visible = False
            self.deselect_all_button.visible = False

    def _show_remove_waveform_modal(self, event):
        if not self.check_buttons.value:
            pn.state.notifications.error("No waveforms selected for removal.")
            return
        self.remove_waveform_modal.open()

    def _remove_waveforms(self):
        """Remove all selected waveforms in this CheckButtonGroup."""
        selected_waveforms = self.check_buttons.value.copy()
        for waveform_name in selected_waveforms:
            self.selector.config.remove_waveform(waveform_name)
            self.check_buttons.options.remove(waveform_name)
        self.check_buttons.value = []
        self.check_buttons.param.trigger("options")

    def _deselect_all(self, event):
        """Deselect all waveforms in this CheckButtonGroup."""
        self.check_buttons.value = []

    def _select_all(self, event):
        """Select all waveforms in this CheckButtonGroup."""
        self.check_buttons.value = self.check_buttons.options

    def _on_add_waveform_button_click(self, event):
        """Show the text input form to add a new waveform."""
        self.new_waveform_panel.is_visible(True)

    def _add_new_waveform(self, event):
        """Add the new waveform to CheckButtonGroup and update the
        WaveformConfiguration."""
        name = self.new_waveform_panel.input.value

        # Add empty waveform to YAML
        yaml_parser = YamlParser()
        new_waveform = yaml_parser.parse_waveforms(f"{name}: [{{}}]")
        # TODO:this try-except block can be replaced with a global error handler later
        try:
            self.selector.config.add_waveform(new_waveform, self.path)
        except ValueError as e:
            pn.state.notifications.error(str(e))
            return

        self.check_buttons.options.append(name)
        self.check_buttons.param.trigger("options")

        self.select_all_button.visible = True
        self.deselect_all_button.visible = True
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
            new_group = self.selector.config.add_group(name, self.path)
        except ValueError:
            pn.state.notifications.error(f"{name!r} already exists in current group.")
            return

        new_path = self.path + [name]
        new_group_ui = self.selector.create_group_ui(new_group, new_path)

        # Check if there exists an accordion already at this level
        existing_accordion = None
        for obj in self.parent_ui.objects:
            if isinstance(obj, pn.Accordion):
                existing_accordion = obj
                break

        # Update UI with new group
        if existing_accordion:
            if name in existing_accordion._names:
                pn.state.notifications.error(f"A group named '{name}' already exists.")
                return

            existing_accordion.append((name, new_group_ui))
        else:
            new_accordion = pn.Accordion((name, new_group_ui))
            self.parent_ui.append(new_accordion)

        self.new_group_panel.is_visible(False)
        self.new_group_panel.clear_input()

    def __panel__(self):
        """Returns the panel UI element."""
        return self.panel
