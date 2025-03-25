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

            # Handle selection changes
            def on_select(event):
                self.waveform_plotter.selected_keys = event.new

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
        # Recursively find and deselect all CheckButtonGroups in the UI structure
        self._deselect_checkbuttons(self.selector)

    def _deselect_checkbuttons(self, widget):
        if isinstance(widget, pn.widgets.CheckButtonGroup):
            widget.value = []  # Deselect the checkbutton group
        else:
            for child in widget:
                self._deselect_checkbuttons(child)
