import panel as pn
import param
from panel.viewable import Viewer
from panel_jstree import Tree

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
    active_group_path = param.List(
        doc="Path to the currently active group (list of group names)",
    )

    def __init__(self, main_gui):
        super().__init__()
        self.main_gui = main_gui
        self.config = main_gui.config
        self.is_removing_waveform = State()
        self._ignore_selection_change = State()

        self.filter_input = pn.widgets.TextInput(
            placeholder="Filter waveforms...", sizing_mode="stretch_width"
        )

        self.tree = Tree(
            data=self._build_tree_data(),
            checkbox=True,
            select_multiple=True,
            cascade=False,
            show_icons=False,
            sizing_mode="stretch_width",
        )
        self.tree.param.watch(self._on_tree_value_change, "value")

        # Flat view for filter results
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

        from waveform_editor.gui.selector.options_button_row import OptionsButtonRow

        self.button_row = OptionsButtonRow(main_gui, self)

        self.panel = pn.Column(
            pn.Row(self.filter_input, clear_filter_button),
            self.button_row,
            pn.Column(self.tree, visible=self.filter_input.param.value_input.rx.not_()),
            self.filtered_results,
            filter_empty_text,
            visible=self.param.visible,
        )

    def _build_tree_data(self):
        """Build jstree data structure from config."""

        def build_group_node(group, parent_path):
            path = parent_path + [group.name]
            node_id = "grp:" + "/".join(path)
            children = [
                {"id": f"wf:{wf_name}", "text": wf_name} for wf_name in group.waveforms
            ]
            children += [build_group_node(sg, path) for sg in group.groups.values()]
            return {
                "id": node_id,
                "text": group.name,
                "children": children,
                "state": {"opened": True},
            }

        return [build_group_node(g, []) for g in self.config.groups.values()]

    def _on_tree_value_change(self, event):
        """Handle changes to tree selection."""
        if self._ignore_selection_change:
            return

        new_value = event.new or []
        old_value = event.old or []

        # Update active group when a group node is newly selected
        new_grp_ids = [
            v for v in new_value if v.startswith("grp:") and v not in old_value
        ]
        if new_grp_ids:
            self.active_group_path = new_grp_ids[-1][4:].split("/")  # strip "grp:"

        wf_names = [v[3:] for v in new_value if v.startswith("wf:")]

        if not self.multiselect:
            old_wf_names = [v[3:] for v in old_value if v.startswith("wf:")]
            newly_added = [n for n in wf_names if n not in old_wf_names]
            new_sel = [newly_added[-1]] if newly_added else wf_names[:1]
            self.set_selection(new_sel)
        else:
            self.set_selection(wf_names)

    def _rebuild_tree(self):
        """Rebuild tree from config, preserving current selection."""
        with self._ignore_selection_change:
            self.tree.data = self._build_tree_data()
            self._sync_tree_selection()

    def _sync_tree_selection(self):
        """Sync tree.value to reflect self.selection.

        Must be called within _ignore_selection_change.
        """
        existing_wf_ids = {f"wf:{wf}" for wf in self.config.waveform_map}
        current_grp = [v for v in (self.tree.value or []) if v.startswith("grp:")]
        valid_wf_ids = [
            f"wf:{n}" for n in self.selection if f"wf:{n}" in existing_wf_ids
        ]
        self.tree.value = current_grp + valid_wf_ids

    def refresh(self):
        """Discard current UI state and re-build from self.config."""
        self.filter_input.value = ""
        self.selection = []
        self.active_group_path = []
        with self._ignore_selection_change:
            self.tree.data = self._build_tree_data()
            self.tree.value = []

    @param.depends("multiselect", watch=True)
    def _multiselect_changed(self):
        if not self.multiselect:
            self.set_selection(self.selection[:1])

    @param.depends("selection", watch=True)
    def _sync_filtered_view(self):
        self.filtered_results.value = [
            s for s in self.selection if s in self.filtered_results.options
        ]

    def _update_filter_view(self, event):
        filter_text = self.filter_input.value_input.lower()
        if not filter_text:
            return
        with self._ignore_selection_change:
            filtered = [w for w in self.config.waveform_map if filter_text in w.lower()]
            self.filtered_results.options = sorted(filtered)
            self._sync_filtered_view()

    def set_selection(self, new_selection: list[str]):
        """Update the active selection and sync the tree."""
        if not self.multiselect:
            assert len(new_selection) <= 1
        with self._ignore_selection_change:
            self.selection = new_selection
            self._sync_tree_selection()

    def remove_group(self, path: list[str]):
        """Remove the UI element for the group at path and update selection."""
        new_sel = [v for v in self.selection if v in self.config.waveform_map]
        self._rebuild_tree()
        if new_sel != self.selection:
            with self.is_removing_waveform:
                self.set_selection(new_sel)
        if self.active_group_path[: len(path)] == path:
            self.active_group_path = []

    def on_select(self, event):
        """Handle selection in the filtered results view."""
        if self._ignore_selection_change:
            return
        if self.multiselect:
            if self.filter_input.value_input:
                preserved = [
                    s for s in self.selection if s not in self.filtered_results.options
                ]
                self.set_selection(preserved + event.new)
            else:
                self.set_selection(event.new)
        else:
            new_selection = [name for name in event.new if name not in event.old]
            self.set_selection(new_selection[:1])

    def __panel__(self):
        return self.panel
