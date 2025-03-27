import panel as pn
import yaml


class WaveformSelector:
    """Class to generate a dynamic waveform selection UI from YAML data."""

    def __init__(self, yaml_data, waveform_plotter, waveform_editor):
        """
        Initialize the waveform selector.

        Args:
            yaml_data (dict): Parsed YAML data.
            waveform_plotter: Reference to the waveform plotter instance for selection
                updates.
        """
        self.waveform_plotter = waveform_plotter
        self.waveform_editor = waveform_editor
        self.selected_dict = {}
        self.previous_selection = {}
        self.yaml_map = {}
        self.selector = self.create_waveform_selector(yaml_data, is_root=True)
        self.edit_waveforms_enabled = False  # Control flag for deselect behavior

    def create_waveform_selector(self, data, is_root=False):
        """Recursively create a Panel UI structure from the YAML."""
        categories = []
        options = []

        if data is None:
            return

        for key, value in data.items():
            if key == "globals":
                continue
            elif "/" in key:
                options.append(key)
                self.yaml_map[key] = value
            else:
                categories.append((key, self.create_waveform_selector(value)))

        content = []
        check_buttons = pn.widgets.CheckButtonGroup(
            value=[],
            options=options,
            button_style="outline",
            button_type="primary",
            sizing_mode="stretch_width",
            orientation="vertical",
            stylesheets=["button {text-align: left!important;}"],
        )

        select_all_button = pn.widgets.ButtonIcon(
            icon="select-all", size="30px", active_icon="check"
        )

        def select_all(event):
            """Select all options in this CheckButtonGroup."""
            check_buttons.value = options

        select_all_button.on_click(select_all)

        deselect_all_button = pn.widgets.ButtonIcon(
            icon="deselect", size="30px", active_icon="check"
        )

        def deselect_all(event):
            """Deselect all options in this CheckButtonGroup."""
            check_buttons.value = []

        deselect_all_button.on_click(deselect_all)

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

        # Widget for adding new waveforms
        new_waveform_button = pn.widgets.ButtonIcon(
            icon="plus", size="30px", active_icon="check"
        )
        new_waveform_input = pn.widgets.TextInput(
            placeholder="Enter name of new waveform"
        )
        add_new_waveform_button = pn.widgets.Button(
            name="Add", sizing_mode="stretch_width"
        )
        new_waveform_panel = pn.Row(new_waveform_input, add_new_waveform_button)
        new_waveform_panel.visible = False

        def on_add_waveform_button_click(event):
            """Show the text input to add a new option."""
            new_waveform_panel.visible = True

        def add_new_waveform(event):
            """Add the new option to CheckButtonGroup."""
            new_waveform = new_waveform_input.value.strip()
            if new_waveform and new_waveform not in check_buttons.options:
                check_buttons.options.append(new_waveform)
                new_waveform_panel.visible = False
                new_waveform_input.value = ""
                check_buttons.param.trigger("options")
                select_all_button.visible = True
                deselect_all_button.visible = True

        new_waveform_button.on_click(on_add_waveform_button_click)
        add_new_waveform_button.on_click(add_new_waveform)

        # Add buttons
        button_row = pn.Row(
            new_waveform_button,
            select_all_button,
            deselect_all_button,
        )

        if not options:
            select_all_button.visible = False
            deselect_all_button.visible = False
        if is_root:
            new_waveform_button.visible = False

        content.append(button_row)
        content.append(new_waveform_panel)
        content.append(check_buttons)

        if categories:
            accordion = pn.Accordion(*categories)
            content.append(accordion)

        return pn.Column(*content, sizing_mode="stretch_width")

    def get_selector(self):
        """Returns the waveform selector UI component."""
        return self.selector

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
