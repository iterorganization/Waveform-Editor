import panel as pn
import yaml


class WaveformSelector:
    """Class to generate a dynamic waveform selection UI from YAML data."""

    def __init__(self, yaml, yaml_map, waveform_plotter, waveform_editor):
        self.waveform_plotter = waveform_plotter
        self.waveform_editor = waveform_editor
        self.selected_dict = {}
        self.previous_selection = {}
        self.yaml_map = yaml_map
        self.yaml = yaml
        self.selector = self.create_waveform_selector(self.yaml, is_root=True)
        self.edit_waveforms_enabled = False

    def create_waveform_selector(self, data, is_root=False, path=None):
        """Recursively create a Panel UI structure from the YAML."""
        if path is None:
            path = []

        groups = []
        waveforms = []

        if data is None:
            data = {}

        for key, value in data.items():
            if key == "globals":
                continue
            elif "/" in key:
                waveforms.append(key)
                self.yaml_map[key] = value
            else:
                # Track path in yaml groups
                new_path = path + [key]
                groups.append(
                    (key, self.create_waveform_selector(value, path=new_path))
                )

        content = []
        check_buttons = pn.widgets.CheckButtonGroup(
            value=[],
            options=waveforms,
            button_style="outline",
            button_type="primary",
            sizing_mode="stretch_width",
            orientation="vertical",
            stylesheets=["button {text-align: left!important;}"],
        )

        # Select all Button
        select_all_button = pn.widgets.ButtonIcon(
            icon="select-all",
            size="30px",
            active_icon="check",
            description="Select all waveforms in this group",
        )

        def select_all(event):
            """Select all options in this CheckButtonGroup."""
            check_buttons.value = waveforms

        select_all_button.on_click(select_all)

        # Deselect all Button
        deselect_all_button = pn.widgets.ButtonIcon(
            icon="deselect",
            size="30px",
            active_icon="check",
            description="Deselect all waveforms in this group",
        )

        def deselect_all(event):
            """Deselect all options in this CheckButtonGroup."""
            check_buttons.value = []

        deselect_all_button.on_click(deselect_all)

        # Add new waveform button
        new_waveform_button = pn.widgets.ButtonIcon(
            icon="plus",
            size="30px",
            active_icon="check",
            description="Add new waveform",
        )
        new_waveform_input = pn.widgets.TextInput(
            placeholder="Enter name of new waveform"
        )
        add_new_waveform_button = pn.widgets.Button(
            name="Add", sizing_mode="stretch_width"
        )
        new_waveform_panel = pn.Row(
            new_waveform_input, add_new_waveform_button, visible=False
        )

        def on_add_waveform_button_click(event, path):
            """Show the text input to add a new option."""
            self.selected_category_path = path
            new_waveform_panel.visible = True

        def add_new_waveform(event):
            """Add the new option to CheckButtonGroup and update the YAML."""
            new_waveform = new_waveform_input.value.strip()
            if new_waveform in self.yaml_map:
                pn.state.notifications.error(
                    f"Waveform {new_waveform!r} already exists!"
                )
                return
            # TODO: Perhaps we should allow this, and distinguish between groups and
            # waveforms in another way
            if "/" not in new_waveform:
                pn.state.notifications.error("A waveform should contain '/'.")
                return
            if new_waveform and new_waveform not in check_buttons.options:
                check_buttons.options.append(new_waveform)

                if self.selected_category_path:
                    self.add_entry_to_yaml(self.selected_category_path, new_waveform)

                new_waveform_panel.visible = False
                new_waveform_input.value = ""
                check_buttons.param.trigger("options")
                select_all_button.visible = True
                deselect_all_button.visible = True

        new_waveform_button.on_click(
            lambda event, path=path: on_add_waveform_button_click(event, path)
        )
        add_new_waveform_button.on_click(add_new_waveform)

        # Add new group button
        new_group_button = pn.widgets.ButtonIcon(
            icon="library-plus",
            size="30px",
            active_icon="check",
            description="Add new group",
        )
        new_group_input = pn.widgets.TextInput(placeholder="Enter name of new group")
        add_new_group_button = pn.widgets.Button(
            name="Add", sizing_mode="stretch_width"
        )
        new_group_panel = pn.Row(new_group_input, add_new_group_button, visible=False)

        def on_add_group_button_click(event, path):
            """Show the text input to add a new option."""
            self.selected_category_path = path
            new_group_panel.visible = True

        def add_new_group(event):
            """Add the new group to the correct place in the UI and YAML."""
            new_group = new_group_input.value.strip()
            if "/" in new_group:
                pn.state.notifications.error("Groups may not contain '/'.")
                return
            parent_ui = self.find_ui_container(
                self.selector, self.selected_category_path
            )
            if parent_ui is None:
                pn.state.notifications.error(
                    "Could not find the parent UI element to create the new group in."
                )
                return

            existing_accordion = None
            for obj in parent_ui.objects:
                if isinstance(obj, pn.Accordion):
                    existing_accordion = obj
                    break

            new_path = self.selected_category_path + [new_group]
            new_group_content = self.create_waveform_selector({}, path=new_path)
            if existing_accordion:
                if new_group in existing_accordion._names:
                    pn.state.notifications.error(
                        f"A group named '{new_group}' already exists."
                    )
                    return

                existing_accordion.append((new_group, new_group_content))
            else:
                new_accordion = pn.Accordion((new_group, new_group_content))
                parent_ui.append(new_accordion)

            if self.selected_category_path:
                self.add_entry_to_yaml(self.selected_category_path, new_group)

            new_group_panel.visible = False
            new_group_input.value = ""

        new_group_button.on_click(
            lambda event, path=path: on_add_group_button_click(event, path)
        )
        add_new_group_button.on_click(add_new_group)

        # Selecting a waveform
        def on_select(event):
            new_selection = event.new
            old_selection = self.previous_selection.get(check_buttons, {})

            newly_selected = {
                key: self.yaml_map[key]
                for key in new_selection
                if key not in old_selection
            }

            if self.edit_waveforms_enabled:
                if newly_selected:
                    newly_selected_key = list(newly_selected.keys())[0]
                    self.deselect_all(exclude=newly_selected_key)

                    # Update code editor with the selected value
                    value = newly_selected[newly_selected_key]
                    if isinstance(value, (int, float)):
                        yaml_dump = f"{newly_selected_key}: {value}"
                    else:
                        yaml_dump = f"{newly_selected_key}:\n{yaml.dump(value)}"
                    self.waveform_editor.code_editor.value = yaml_dump
            else:
                deselected = [key for key in old_selection if key not in new_selection]
                for key in deselected:
                    self.selected_dict.pop(key, None)

                for key, value in newly_selected.items():
                    self.selected_dict[key] = value

            self.waveform_plotter.selected_waveforms = self.selected_dict
            self.waveform_plotter.param.trigger("selected_waveforms")
            self.previous_selection[check_buttons] = new_selection

        check_buttons.param.watch(on_select, "value")

        # Add row of option buttons
        button_row = pn.Row(
            new_waveform_button,
            new_group_button,
            select_all_button,
            deselect_all_button,
        )

        content.append(button_row)
        content.append(new_waveform_panel)
        content.append(new_group_panel)
        content.append(check_buttons)

        if groups:
            accordion = pn.Accordion(*groups)
            content.append(accordion)

        # Set visibility
        if not waveforms:
            select_all_button.visible = False
            deselect_all_button.visible = False
        if is_root:
            if self.yaml != {}:
                new_group_button.visible = True
            else:
                new_group_button.visible = False
            new_waveform_button.visible = False
        return pn.Column(*content, sizing_mode="stretch_width")

    def get_selector(self):
        """Returns the waveform selector UI component."""
        return self.selector

    def add_entry_to_yaml(self, category_path, new_entry):
        """Navigate YAML tree and insert new waveform correctly."""
        current = self.yaml
        for key in category_path:
            current = current.setdefault(key, {})

        if "/" in new_entry:
            current[new_entry] = [{}]
            self.yaml_map[new_entry] = [{}]
        else:
            current[new_entry] = {}

    def find_ui_container(self, widget, category_path):
        """
        Recursively search for the correct UI container based on the category path.

        Args:
            widget: The current widget to search in.
            category_path: List of category keys representing the path.

        Returns:
            The found UI container where new groups should be added.
        """
        if not category_path:
            return widget

        current_category = category_path[0]

        if isinstance(widget, pn.Accordion):
            for idx, section in enumerate(widget.objects):
                section_title = widget._names[idx]

                if section_title == current_category and isinstance(section, pn.Column):
                    return self.find_ui_container(section, category_path[1:])

        if isinstance(widget, pn.Column):
            for child in widget.objects:
                if isinstance(child, (pn.Accordion, pn.Column)):
                    result = self.find_ui_container(child, category_path)
                    if result:
                        return result

        return None

    def deselect_all(self, exclude=None):
        """Deselect all options in all CheckButtonGroup widgets, excluding a certain
        item."""
        if exclude:
            self.selected_dict = {exclude: self.yaml_map[exclude]}
        else:
            self.selected_dict = {}

        self._deselect_checkbuttons(self.selector, exclude)
        self.waveform_plotter.selected_waveforms = self.selected_dict

    def _deselect_checkbuttons(self, widget, exclude):
        """Helper function to recursively find and deselect all CheckButtonGroup
        widgets."""
        if isinstance(widget, pn.widgets.CheckButtonGroup):
            if exclude in widget.value:
                widget.value = [exclude]
            else:
                widget.value = []
        else:
            for child in widget:
                # Skip select/deselect buttons row
                if isinstance(widget, pn.Row):
                    continue
                self._deselect_checkbuttons(child, exclude)
