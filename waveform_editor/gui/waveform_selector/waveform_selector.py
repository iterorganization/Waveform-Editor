import panel as pn

from waveform_editor.gui.waveform_selector.options_button_row import OptionsButtonRow


class WaveformSelector:
    """Panel containing a dynamic waveform selection UI from YAML data."""

    def __init__(self, config, waveform_plotter, waveform_editor):
        self.config = config
        self.waveform_plotter = waveform_plotter
        self.waveform_editor = waveform_editor
        self.selected_dict = {}
        self.previous_selection = {}
        self.edit_waveforms_enabled = False
        self.selector = self.create_waveform_selector()

    def create_waveform_selector(self):
        ui_content = []
        for group in self.config.groups.values():
            path = [group.name]
            ui_content.append((group.name, self.create_group_ui(group, path)))
        return pn.Accordion(*ui_content, sizing_mode="stretch_width")

    def create_group_ui(self, group, path):
        """Recursively create a Panel UI structure from the YAML.

        Args:
            data: Dictionary containing the yaml data.
            is_root: Whether function is called from the root level of the YAML.
            path: The path of the nested groups in the YAML data, as a list of strings.
        """

        # Build UI of each group recursively
        inner_groups_ui = []
        for inner_group in group.groups.values():
            new_path = path + [inner_group.name]
            inner_groups_ui.append(
                (inner_group.name, self.create_group_ui(inner_group, new_path))
            )

        # List of waveforms to select
        waveforms = list(group.waveforms.keys())
        check_buttons = pn.widgets.CheckButtonGroup(
            value=[],
            options=waveforms,
            button_style="outline",
            button_type="primary",
            sizing_mode="stretch_width",
            orientation="vertical",
            stylesheets=["button {text-align: left!important;}"],
        )
        check_buttons.param.watch(
            lambda event: self.on_select(event, check_buttons, path), "value"
        )

        # Create row of options for each group
        button_row = OptionsButtonRow(self, check_buttons, waveforms, path)

        # Add buttons, waveform list and groups to UI content list
        ui_content = []
        ui_content.append(button_row.get())
        ui_content.append(check_buttons)

        # Create accordion to store the inner groups UI objects into
        if group.groups:
            accordion = pn.Accordion(*inner_groups_ui)
            ui_content.append(accordion)

        parent_container = pn.Column(*ui_content, sizing_mode="stretch_width")
        button_row.parent_ui = parent_container

        return parent_container

    def on_select(self, event, check_buttons, path):
        """Handles the selection and deselection of waveforms in the check button
        group."""
        new_selection = event.new
        old_selection = self.previous_selection.get(check_buttons, {})

        newly_selected = {
            key: self.config.waveform_map[key]
            for key in new_selection
            if key not in old_selection
        }

        if self.edit_waveforms_enabled:
            self.select_in_editor(newly_selected, path)
        else:
            self.select_in_viewer(newly_selected, new_selection, old_selection)

        self.waveform_plotter.selected_waveforms = self.selected_dict
        self.waveform_plotter.param.trigger("selected_waveforms")
        self.previous_selection[check_buttons] = check_buttons.value

    def select_in_editor(self, newly_selected, path):
        if newly_selected:
            newly_selected_key = list(newly_selected.keys())[0]
            self.deselect_all(exclude=newly_selected_key)

            # Update code editor with the selected value
            waveform = newly_selected[newly_selected_key]
            self.waveform_editor.code_editor.value = waveform.yaml_str
            self.waveform_editor.path = path
        else:
            self.waveform_editor.set_default()

    def select_in_viewer(self, newly_selected, new_selection, old_selection):
        deselected = [key for key in old_selection if key not in new_selection]
        for key in deselected:
            self.selected_dict.pop(key, None)

        for key, value in newly_selected.items():
            self.selected_dict[key] = value

    def deselect_all(self, exclude=None):
        """Deselect all options in all CheckButtonGroup widgets, excluding a certain
        item."""
        if exclude:
            self.selected_dict = {exclude: self.config.waveform_map[exclude]}
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

    def get(self):
        """Returns the waveform selector UI component."""
        return self.selector
