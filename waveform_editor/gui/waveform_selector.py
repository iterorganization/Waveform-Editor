import panel as pn


class WaveformSelector:
    """Class to generate a dynamic waveform selection UI from YAML data."""

    def __init__(self, yaml_data, waveform_plotter):
        """
        Initialize the waveform selector.

        Args:
            yaml_data (dict): Parsed YAML data.
            waveform_plotter: Reference to the waveform plotter instance for selection
                updates.
        """
        self.waveform_plotter = waveform_plotter
        self.selected_keys = []
        self.previous_selection = {}
        self.selector = self.create_waveform_selector(yaml_data)

    def create_waveform_selector(self, data):
        """Recursively create a Panel UI structure from the YAML."""
        categories = []
        options = []

        for key, value in data.items():
            if key == "globals":
                continue
            elif "/" in key:
                options.append(key)
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

            # Only changes for a single CheckButtonGroup are provided in event.new, so
            # we need to track the state of the selected keys for other
            # CheckButtonGroups
            def on_select(event):
                new_selection = event.new
                old_selection = self.previous_selection.get(check_buttons, [])
                newly_selected = [
                    key for key in new_selection if key not in old_selection
                ]
                deselected = [key for key in old_selection if key not in new_selection]
                self.selected_keys = list(
                    set(self.selected_keys + newly_selected) - set(deselected)
                )
                self.waveform_plotter.selected_keys = self.selected_keys
                self.previous_selection[check_buttons] = new_selection

            check_buttons.param.watch(on_select, "value")
            content.append(check_buttons)

        if categories:
            accordion = pn.Accordion(*categories)
            content.append(accordion)

        return pn.Column(*content, sizing_mode="stretch_width")

    def get_selector(self):
        """Returns the waveform selector UI component."""
        return self.selector

    def deselect_all(self):
        """Deselect all options in all CheckButtonGroup widgets."""
        self.selected_keys = []
        self._deselect_checkbuttons(self.selector)
        self.waveform_plotter.selected_keys = self.selected_keys

    def _deselect_checkbuttons(self, widget):
        """Helper function to recursively find and deselect all CheckButtonGroup
        widgets."""
        if isinstance(widget, pn.widgets.CheckButtonGroup):
            widget.value = []
        else:
            for child in widget:
                self._deselect_checkbuttons(child)
