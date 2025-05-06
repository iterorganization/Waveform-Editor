import panel as pn
from panel.viewable import Viewer

from waveform_editor.gui.selector.confirm_modal import ConfirmModal
from waveform_editor.gui.selector.options_button_row import OptionsButtonRow


class WaveformSelector(Viewer):
    """Panel containing a dynamic waveform selection UI from YAML data."""

    def __init__(self, main_gui):
        self.main_gui = main_gui
        self.config = self.main_gui.config
        self.plotter = self.main_gui.plotter
        self.editor = self.main_gui.editor
        self.confirm_modal = ConfirmModal()
        self.ui_selector = pn.Accordion(sizing_mode="stretch_width")
        self.prev_selection = []
        self.ignore_tab_watcher = False
        self.ignore_select_watcher = False
        self.warning_message = (
            "# **⚠️ Warning**  \nYou did not save your changes. "
            "Leaving now will discard any changes you made to this waveform."
            "   \n\n**Are you sure you want to continue?**"
        )
        self._create_root_button_row()

    def create_waveform_selector_ui(self):
        """Creates a UI for the selector sidebar, containing accordions for each
        group in the config, option buttons, and CheckButtonGroups for the lists of
        waveforms.
        """
        self.root_button_row.new_group_button.visible = True
        self.ui_selector.objects = [
            self.create_group_ui(group, [group.name], parent_accordion=self.ui_selector)
            for group in self.config.groups.values()
        ]

    def on_tab_change(self, event):
        """Change selection behavior, depending on which tab is selected."""
        if event.new != self.main_gui.EDIT_WAVEFORMS_TAB and self.editor.has_changed():
            self.confirm_modal.show(
                self.warning_message,
                on_confirm=self.confirm_tab_change,
                on_cancel=self.cancel_tab_change,
            )
            return
        if not self.ignore_tab_watcher:
            self.confirm_tab_change()

    def confirm_tab_change(self):
        self.deselect_all(ignore_watch=True)
        self.editor.set_empty()

    def cancel_tab_change(self):
        """Revert the selection Select the edit waveforms tab."""
        # Ensure apply_tab_change is not called again through watcher
        self.ignore_tab_watcher = True
        self.main_gui.tabs.active = self.main_gui.EDIT_WAVEFORMS_TAB
        self.ignore_tab_watcher = False

    def create_group_ui(self, group, path, parent_accordion=None):
        """Recursively create a Panel UI structure from the YAML.

        Args:
            group: The group to add the new group to.
            path: The path of the nested groups in the YAML data, as a list of strings.
        """

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
        check_buttons.param.watch(self.on_select, "value")

        # Create accordion to store the inner groups UI objects into
        if group.groups:
            inner_groups_ui = []
            accordion = pn.Accordion()
            for inner_group in group.groups.values():
                new_path = path + [inner_group.name]
                inner_groups_ui.append(
                    self.create_group_ui(
                        inner_group, new_path, parent_accordion=accordion
                    )
                )
            accordion.objects = inner_groups_ui

        parent_container = pn.Column(sizing_mode="stretch_width", name=group.name)

        # Create row of options for each group
        button_row = OptionsButtonRow(
            self.main_gui, check_buttons, path, parent_accordion=parent_accordion
        )

        # Add buttons, waveform list and groups to UI column
        ui_content = [button_row, check_buttons]
        if group.groups:
            ui_content.append(accordion)
        parent_container.objects = ui_content

        return parent_container

    def on_select(self, event):
        """Handles the selection and deselection of waveforms in the check button
        group.

        Args:
            event: list containing the new selection.
        """
        if self.ignore_select_watcher:
            return
        new_selection = event.new
        old_selection = event.old

        # Find which waveform was newly selected
        newly_selected = {
            key: self.config[key] for key in new_selection if key not in old_selection
        }
        deselected = [key for key in old_selection if key not in new_selection]
        if self.main_gui.tabs.active == self.main_gui.EDIT_WAVEFORMS_TAB:
            if self.editor.has_changed():
                self.confirm_modal.show(
                    self.warning_message,
                    on_confirm=lambda: self.confirm_on_select(
                        newly_selected, deselected
                    ),
                    on_cancel=lambda: self.deselect_all(
                        include=self.prev_selection, ignore_watch=True
                    ),
                )
                return
            self.confirm_on_select(newly_selected, deselected)

        self.update_plotter(newly_selected, deselected)

    def update_plotter(self, newly_selected, deselected):
        for key in deselected:
            del self.plotter.plotted_waveforms[key]

        for key, value in newly_selected.items():
            self.plotter.plotted_waveforms[key] = value

        self.plotter.param.trigger("plotted_waveforms")

    def confirm_on_select(self, newly_selected, deselected):
        """Only allow for a single waveform to be selected. All waveforms except for
        the newly selected waveform will be deselected.

        Args:
            newly_selected: The newly selected waveform.
        """
        if newly_selected:
            newly_selected_key = list(newly_selected.keys())[0]
            self.deselect_all(exclude=newly_selected_key, ignore_watch=True)

            # Update code editor with the selected value
            waveform = newly_selected[newly_selected_key]
            self.editor.set_value(waveform.get_yaml_string())
            if len(newly_selected) != 1:
                raise ValueError("Expected only a single new waveform to be selected.")
            self.prev_selection = next(iter(newly_selected))
        self.update_plotter(newly_selected, deselected)
        if not self.plotter.plotted_waveforms:
            self.editor.set_empty()

    def deselect_all(self, exclude=None, ignore_watch=False, include=None):
        """Deselect all options in all CheckButtonGroups. A waveform name can be
        provided to be excluded from deselection.

        Args:
            exclude: The name of a waveform to exclude from deselection.
        """
        if ignore_watch:
            self.ignore_select_watcher = True
        self._deselect_checkbuttons(self.ui_selector, exclude, include)
        if ignore_watch:
            self.ignore_select_watcher = False

    def _create_root_button_row(self):
        """Creates a options button row at the root level of the selector groups."""
        self.root_button_row = OptionsButtonRow(self.main_gui, None, [], visible=False)

    def _deselect_checkbuttons(self, widget, exclude, include):
        """Helper function to recursively find and deselect all CheckButtonGroup
        widgets.

        Args:
            widget: The widget in which to deselect the checkbuttons.
            exclude: The waveform to exclude from deselection.
        """
        if isinstance(widget, pn.widgets.CheckButtonGroup):
            if exclude in widget.value:
                widget.value = [exclude]
            else:
                widget.value = []

            if include in widget.options and include not in widget.value:
                widget.value.append(include)
            widget.param.trigger("value")
        elif isinstance(widget, (pn.Column, pn.Accordion)):
            for child in widget:
                # Skip select/deselect buttons row
                if isinstance(widget, pn.Row):
                    continue
                self._deselect_checkbuttons(child, exclude, include)

    def __panel__(self):
        """Returns the waveform selector UI component."""
        return pn.Column(self.root_button_row, self.ui_selector, self.confirm_modal)
