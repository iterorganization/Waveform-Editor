import panel as pn
import yaml

from waveform_editor.gui.waveform_selector.options_button_row import OptionsButtonRow


class WaveformSelector:
    """Class to generate a dynamic waveform selection UI from YAML data."""

    def __init__(self, yaml, yaml_map, waveform_plotter, waveform_editor):
        self.waveform_plotter = waveform_plotter
        self.waveform_editor = waveform_editor
        self.selected_dict = {}
        self.previous_selection = {}
        self.yaml_map = yaml_map
        self.yaml = yaml
        self.edit_waveforms_enabled = False
        self.selector = self.create_waveform_selector(self.yaml, is_root=True)

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

        # Create options row for each group
        button_row = OptionsButtonRow(
            self,
            self.yaml,
            self.yaml_map,
            check_buttons,
            waveforms,
            path,
        )
        content.append(button_row.get())
        content.append(check_buttons)

        if groups:
            accordion = pn.Accordion(*groups)
            content.append(accordion)

        parent_container = pn.Column(*content, sizing_mode="stretch_width")
        button_row.parent_ui = parent_container

        # Set visibility of button row
        if is_root:
            if self.yaml != {}:
                button_row.new_group_button.visible = True
            else:
                button_row.new_group_button.visible = False
            button_row.new_waveform_button.visible = False
        return parent_container

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
