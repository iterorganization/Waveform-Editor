import panel as pn
import param
from panel import bind
from panel.viewable import Viewer

from waveform_editor.gui.selector.selection_group import SelectionGroup
from waveform_editor.util import State


class WaveformSelector(Viewer):
    """Panel containing a dynamic waveform selection UI from YAML data."""

    visible = param.Boolean(allow_refs=True)
    selection = param.List(
        doc="List of selected waveform names. Use `set_selection` to set.",
    )
    multiselect = param.Boolean(
        True,
        doc="Allow selecting multiple waveforms",
        allow_refs=True,
    )

    def __init__(self, main_gui):
        super().__init__()
        self.main_gui = main_gui  # options_button_row needs the modals from main_gui
        self.config = main_gui.config
        self.is_removing_waveform = State()
        self._ignore_selection_change = State()
        self.selection = []

        # UI
        self.selection_group = SelectionGroup(self, self.config, [])

        # Flat selection group for filtered results
        self.filter_input = pn.widgets.TextInput(
            placeholder="Filter waveforms...", sizing_mode="stretch_width"
        )
        self.filtered_results = pn.widgets.CheckButtonGroup(
            value=[],
            options=[],
            button_type="primary",
            button_style="outline",
            sizing_mode="stretch_width",
            orientation="vertical",
            stylesheets=["button {text-align: left!important;}"],
        )
        self.filtered_results.param.watch(self.on_select, "value")
        self.param.watch(self._sync_filtered_view, "selection")

        # The main view, which dynamically switches between tree and filtered list
        view = bind(self._get_view, self.filter_input.param.value_input)
        self.panel = pn.Column(self.filter_input, view, visible=self.param.visible)

    def _get_view(self, filter_text: str):
        """
        Return the appropriate view based on whether a filter is active.
        This function is bound to the filter_input's value.
        """
        if not filter_text:
            return self.selection_group
        else:
            all_waveforms = self.selection_group.get_all_waveforms()
            filtered = [w for w in all_waveforms if filter_text.lower() in w.lower()]
            self.filtered_results.options = sorted(filtered)
            # Ensure selection is maintained in the filtered view
            self._sync_filtered_view()
            return self.filtered_results

    def refresh(self):
        """Discard the current UI state and re-build from self.config.

        Should be called after loading a new configuration.
        """
        self.filter_input.value = ""
        self.selection_group = SelectionGroup(self, self.config, [])
        # The dynamic view will update automatically due to pn.bind
        self.panel[1] = bind(self._get_view, self.filter_input.param.value_input)
        self.selection = []

    @param.depends("multiselect", watch=True)
    def _multiselect_changed(self):
        """Update selection when multiselect True -> False: keep at most one item."""
        if not self.multiselect:
            self.set_selection(self.selection[:1])

    def _sync_filtered_view(self, *events):
        """Syncs the main selection list to the filtered view's value."""
        self.filtered_results.value = [
            s for s in self.selection if s in self.filtered_results.options
        ]

    def set_selection(self, new_selection: list[str]):
        """Update the active selection."""
        with self._ignore_selection_change:  # Don't listen to the widget callbacks
            if not self.multiselect:
                assert len(new_selection) <= 1
            self.selection = new_selection

    def remove_group(self, path: list[str]):
        """Remove the UI element for the group at the specified path."""
        parent_group, group_ui = None, self.selection_group
        for part in path:
            parent_group, group_ui = group_ui, group_ui.selection_groups[part]

        selection_to_delete = group_ui.get_selection(True)
        parent_group.remove_group(path[-1])
        del group_ui
        if selection_to_delete:
            new_sel = [val for val in self.selection if val not in selection_to_delete]
            with self.is_removing_waveform:  # Flag that we're removing waveforms
                self.set_selection(new_sel)

    def on_select(self, event):
        """Handles the selection and deselection of waveforms in the check button
        groups.

        Args:
            event: list containing the new selection.
        """
        if self._ignore_selection_change:
            return

        if self.multiselect:
            # Determine if we are in filtered view or tree view.
            if self.filter_input.value_input:
                preserved_selection = [
                    s for s in self.selection if s not in self.filtered_results.options
                ]
                self.selection = preserved_selection + event.new
            else:  # Just update all selected
                self.selection = self.selection_group.get_selection(True)
        else:  # Check which one is new and deselect anything else
            new_selection = [name for name in event.new if name not in event.old]
            assert len(new_selection) <= 1
            self.set_selection(new_selection)

    def __panel__(self):
        """Returns the waveform selector UI component."""
        return self.panel
