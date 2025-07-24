import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.selector.selection_group import SelectionGroup
from waveform_editor.util import State


class WaveformSelector(Viewer):
    """Panel containing a dynamic waveform selection UI from YAML data."""

    visible = param.Boolean(default=True, allow_refs=True)
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

        # UI
        self.filter_input = pn.widgets.TextInput(
            placeholder="Filter waveforms...", sizing_mode="stretch_width"
        )
        self.selection_group = SelectionGroup(self, self.config, [])
        self.selection_group.visible = self.filter_input.param.value_input.rx.not_()

        # Flat selection group for filtered results
        self.filtered_results = pn.widgets.CheckButtonGroup(
            button_type="primary",
            button_style="outline",
            sizing_mode="stretch_width",
            orientation="vertical",
            visible=self.filter_input.param.value_input.rx.bool(),
            stylesheets=["button {text-align: left!important;}"],
        )
        clear_filter_button = pn.widgets.ButtonIcon(
            icon="filter-off",
            size="25px",
            active_icon="check",
            margin=(10, 0, 0, 0),
            description="Clear filter",
            visible=self.filter_input.param.value_input.rx.bool(),
            on_click=lambda event: setattr(self.filter_input, "value_input", ""),
        )

        filter_empty_text = pn.pane.Markdown(
            "_No waveforms found_",
            visible=pn.bind(
                lambda text, opts: bool(text) and not opts,
                self.filter_input.param.value_input,
                self.filtered_results.param.options,
            ),
        )
        self.filtered_results.param.watch(self.on_select, "value")
        self.filter_input.param.watch(self._update_filter_view, "value_input")

        self.panel = pn.Column(
            pn.Row(self.filter_input, clear_filter_button),
            self.selection_group,
            self.filtered_results,
            filter_empty_text,
            visible=self.param.visible,
        )

    def _update_filter_view(self, event):
        """Update the appropriate view based on whether a filter is active."""
        filter_text = self.filter_input.value_input.lower()
        if not filter_text:
            return

        with self._ignore_selection_change:
            filtered = [w for w in self.config.waveform_map if filter_text in w.lower()]
            self.filtered_results.options = sorted(filtered)
            self._sync_filtered_view()

    def refresh(self):
        """Discard the current UI state and re-build from self.config.

        Should be called after loading a new configuration.
        """
        self.filter_input.value = ""
        self.selection_group = SelectionGroup(self, self.config, [])
        self.selection_group.visible = self.filter_input.param.value_input.rx.not_()
        self.panel[1] = self.selection_group
        self.selection = []

    @param.depends("multiselect", watch=True)
    def _multiselect_changed(self):
        """Update selection when multiselect True -> False: keep at most one item."""
        if not self.multiselect:
            self.set_selection(self.selection[:1])

    @param.depends("selection", watch=True)
    def _sync_filtered_view(self):
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
            if self.filter_input.value_input:
                preserved_selection = [
                    s for s in self.selection if s not in self.filtered_results.options
                ]
                self.set_selection(preserved_selection + event.new)
            else:  # Just update all selected
                self.selection = self.selection_group.get_selection(True)
        else:  # Check which one is new and deselect anything else
            new_selection = [name for name in event.new if name not in event.old]
            assert len(new_selection) <= 1
            self.set_selection(new_selection)

    def __panel__(self):
        """Returns the waveform selector UI component."""
        return self.panel
