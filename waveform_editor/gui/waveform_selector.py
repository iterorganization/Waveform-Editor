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
        self.selected_keys = []
        self.previous_selection = {}
        self.yaml_map = {}
        self.selector = self.create_waveform_selector(yaml_data)
        self.deselect_logic_enabled = False  # Control flag for deselect behavior

    def enable_deselect_logic(self, enable):
        """Enable or disable the deselect logic based on the tab selection."""
        self.deselect_logic_enabled = enable

    def create_waveform_selector(self, data):
        """Recursively create a Panel UI structure from the YAML."""
        categories = []
        options = []

        for key, value in data.items():
            if key == "globals":
                continue
            elif "/" in key:
                options.append(key)
                self.yaml_map[key] = value
            else:
                categories.append((key, self.create_waveform_selector(value)))

        content = []
        if options:
            check_buttons = pn.widgets.CheckButtonGroup(
                value=[],
                options=options,
                button_style="outline",
                button_type="primary",
                sizing_mode="stretch_width",
                orientation="vertical",
                stylesheets=["button {text-align: left!important;}"],
            )

            # Select all button
            select_all_button = pn.widgets.Button(
                name="Select All", button_type="success", width=100
            )

            def select_all(event):
                """Select all options in this CheckButtonGroup."""
                check_buttons.value = options

            select_all_button.on_click(select_all)

            # Deselect all button
            deselect_all_button = pn.widgets.Button(
                name="Deselect All", button_type="danger", width=100
            )

            def deselect_all(event):
                """Deselect all options in this CheckButtonGroup."""
                check_buttons.value = []

            deselect_all_button.on_click(deselect_all)

            def on_select(event):
                new_selection = event.new
                old_selection = self.previous_selection.get(check_buttons, [])
                newly_selected = [
                    key for key in new_selection if key not in old_selection
                ]
                if self.deselect_logic_enabled:
                    # Deselect all except for newly_selected
                    if newly_selected:
                        newly_selected = newly_selected[0]
                        self.deselect_all(exclude=newly_selected)

                        value = self.yaml_map[newly_selected]
                        if isinstance(value, (int, float)):
                            yaml_dump = f"{newly_selected}: {value}"
                        else:
                            yaml_dump = f"{newly_selected}:\n{yaml.dump(value)}"
                        self.waveform_editor.code_editor.value = yaml_dump
                else:
                    deselected = [
                        key for key in old_selection if key not in new_selection
                    ]
                    self.selected_keys = list(
                        set(self.selected_keys + newly_selected) - set(deselected)
                    )
                    self.waveform_plotter.selected_keys = self.selected_keys
                self.previous_selection[check_buttons] = new_selection

            check_buttons.param.watch(on_select, "value")

            button_row = pn.Row(select_all_button, deselect_all_button)
            content.append(button_row)
            content.append(check_buttons)

        if categories:
            accordion = pn.Accordion(*categories)
            content.append(accordion)

        return pn.Column(*content, sizing_mode="stretch_width")

    def get_selector(self):
        """Returns the waveform selector UI component."""
        return self.selector

    def deselect_all(self, exclude=None):
        """Deselect all options in all CheckButtonGroup widgets, excluding certain
        items."""
        if exclude:
            self.selected_keys = [exclude]
        else:
            self.selected_keys = []
        self._deselect_checkbuttons(self.selector, exclude)
        self.waveform_plotter.selected_keys = self.selected_keys

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
