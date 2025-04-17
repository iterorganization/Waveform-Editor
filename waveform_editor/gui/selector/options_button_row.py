import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.selector.text_input_form import TextInputForm
from waveform_editor.yaml_parser import YamlParser


class OptionsButtonRow(Viewer):
    visible = param.Boolean(
        default=True,
        doc="The visibility of the option button row.",
    )

    def __init__(
        self,
        main_gui,
        check_buttons,
        path,
        parent_accordion=None,
        visible=True,
    ):
        super().__init__()
        self.main_gui = main_gui
        self.parent_accordion = parent_accordion
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

        if self.check_buttons and not self.check_buttons.options:
            self._show_filled_options(False)
        self.param.watch(self.is_visible, "visible")
        self.visible = visible

    def is_visible(self, event):
        """Set the visibility of the option buttons."""
        self.new_waveform_button.visible = self.visible
        self.remove_waveform_button.visible = self.visible
        self.new_group_button.visible = self.visible
        self.select_all_button.visible = self.visible
        self.deselect_all_button.visible = self.visible
        self.remove_group_button.visible = self.visible

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
            f"**{self.path[-1]}** group?",
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
            f"""Are you sure you want to delete the **{self.path[-1]}** group?  
        This will also remove all waveforms and subgroups in this group!""",
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
        yaml_parser = YamlParser()
        new_waveform = yaml_parser.parse_waveforms(f"{name}: [{{}}]")
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

        # Create new group in configuration
        try:
            new_group = self.main_gui.selector.config.add_group(name, self.path)
        except ValueError as e:
            pn.state.notifications.error(str(e))
            return

        # Create new group in UI
        new_path = self.path + [name]
        existing_accordion = self._get_existing_accordion()
        new_group_ui = self.main_gui.selector.create_group_ui(
            new_group, new_path, parent_accordion=existing_accordion
        )
        existing_accordion.append((name, new_group_ui))

        self.new_group_panel.is_visible(False)
        self.new_group_panel.clear_input()

    def _get_existing_accordion(self):
        """
        Returns an existing Accordion at the current path or creates one if absent.
        """
        if self.parent_accordion is None:
            return self.main_gui.selector.ui_selector

        for column in self.parent_accordion:
            if column.name == self.path[-1]:
                existing_accordion = None
                for obj in column.objects:
                    if isinstance(obj, pn.Accordion):
                        existing_accordion = obj
                if not existing_accordion:
                    existing_accordion = pn.Accordion()
                    column.append(existing_accordion)
                break
        return existing_accordion

    def __panel__(self):
        """Returns the panel UI element."""
        return self.panel
