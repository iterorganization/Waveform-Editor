import panel as pn

from waveform_editor.gui.waveform_selector.text_input_form import TextInputForm


class OptionsButtonRow:
    def __init__(self, selector, check_buttons, waveforms, path):
        self.selector = selector
        self.parent_ui = None
        self.check_buttons = check_buttons
        self.waveforms = waveforms
        self.path = path

        # 'Select all' Button
        self.select_all_button = pn.widgets.ButtonIcon(
            icon="select-all",
            size="30px",
            active_icon="check",
            description="Select all waveforms in this group",
        )
        self.select_all_button.on_click(self._select_all)

        # 'Deselect all' Button
        self.deselect_all_button = pn.widgets.ButtonIcon(
            icon="deselect",
            size="30px",
            active_icon="check",
            description="Deselect all waveforms in this group",
        )
        self.deselect_all_button.on_click(self._deselect_all)

        # 'Add new waveform' button
        self.new_waveform_button = pn.widgets.ButtonIcon(
            icon="plus",
            size="30px",
            active_icon="check",
            description="Add new waveform",
        )
        self.new_waveform_panel = TextInputForm(
            "Enter name of new waveform", is_visible=False
        )
        self.new_waveform_button.on_click(self._on_add_waveform_button_click)
        self.new_waveform_panel.button.on_click(self._add_new_waveform)

        # 'Add new group' button
        self.new_group_button = pn.widgets.ButtonIcon(
            icon="library-plus",
            size="30px",
            active_icon="check",
            description="Add new group",
        )
        self.new_group_panel = TextInputForm(
            "Enter name of new group", is_visible=False
        )
        self.new_group_button.on_click(self._on_add_group_button_click)
        self.new_group_panel.button.on_click(self._add_new_group)

        # Combine all into a button row
        option_buttons = pn.Row(
            self.new_waveform_button,
            self.new_group_button,
            self.select_all_button,
            self.deselect_all_button,
        )
        self.panel = pn.Column(
            option_buttons, self.new_waveform_panel.get(), self.new_group_panel.get()
        )

        if not self.waveforms:
            self.select_all_button.visible = False
            self.deselect_all_button.visible = False

    def _deselect_all(self, event):
        """Deselect all options in this CheckButtonGroup."""
        self.check_buttons.value = []

    def _select_all(self, event):
        """Select all options in this CheckButtonGroup."""
        self.check_buttons.value = self.waveforms

    def _on_add_waveform_button_click(self, event):
        """Show the text input form to add a new waveform."""
        self.new_waveform_panel.is_visible(True)

    def _add_new_waveform(self, event):
        """Add the new waveform to CheckButtonGroup and update the YAML."""
        name = self.new_waveform_panel.input.value
        if name in self.selector.yaml_map:
            pn.state.notifications.error(f"Waveform {name!r} already exists!")
            return
        # TODO: Perhaps we should allow this, and distinguish between groups and
        # waveforms in another way
        if "/" not in name:
            pn.state.notifications.error("The name of a waveform should contain '/'.")
            return

        self.check_buttons.options.append(name)

        # Add empty waveform to YAML
        self._add_entry_to_yaml(name, [{}])

        self.check_buttons.param.trigger("options")
        self.new_waveform_panel.clear_input()

        self.select_all_button.visible = True
        self.deselect_all_button.visible = True
        self.new_waveform_panel.is_visible(False)

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

        existing_accordion = None
        for obj in self.parent_ui.objects:
            if isinstance(obj, pn.Accordion):
                existing_accordion = obj
                break

        new_path = self.path + [name]
        new_group = self.selector.create_waveform_selector({}, path=new_path)

        # Update UI
        if existing_accordion:
            if name in existing_accordion._names:
                pn.state.notifications.error(f"A group named '{name}' already exists.")
                return

            existing_accordion.append((name, new_group))
        else:
            new_accordion = pn.Accordion((name, new_group))
            self.parent_ui.append(new_accordion)

        # Add empty group to YAML
        self._add_entry_to_yaml(name, {}, is_waveform=False)

        self.new_group_panel.is_visible(False)
        self.new_group_panel.clear_input()

    def _add_entry_to_yaml(self, key, value, is_waveform=True):
        """Navigate YAML tree and insert new group or waveform in the YAML. If entry is
        a waveform, it will also be added to the YAML map.

        Args:
            key: name of the waveform/group.
            value: value of the waveform/group.
            is_waveform: Boolean representing whether to add a group or a waveform.
        """
        current = self.selector.yaml
        for key in self.path:
            current = current[key]

        if is_waveform:
            self.selector.yaml_map[key] = value
        current[key] = value

    def get(self):
        """Returns the panel UI element."""
        return self.panel
