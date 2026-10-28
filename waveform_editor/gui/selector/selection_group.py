from typing import TYPE_CHECKING

import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.group import WaveformGroup
from waveform_editor.gui.selector.options_button_row import OptionsButtonRow

if TYPE_CHECKING:
    from waveform_editor.gui.selector.selector import WaveformSelector

_BASE_STYLESHEET = "button {text-align: left!important;}"


class SelectionGroup(Viewer):
    """User Interface for selecting waveforms in a single waveform group"""

    visible = param.Boolean(True, allow_refs=True)

    def __init__(
        self,
        selector: "WaveformSelector",
        group: WaveformConfiguration | WaveformGroup,
        path: list[str],
    ) -> None:
        name = getattr(group, "name", "")
        super().__init__(name=name)

        self.selector = selector
        self.group = group
        self.path = path
        self.is_root = not path

        # Waveform selector
        if self.is_root:  # We have no waveforms
            self.waveform_selector = None
            self.has_waveforms = False
        else:
            self.waveform_selector = pn.widgets.CheckButtonGroup(
                value=[],
                options=list(group.waveforms.keys()),
                button_type="primary",
                button_style="outline",
                sizing_mode="stretch_width",
                orientation="vertical",
                stylesheets=[_BASE_STYLESHEET],
            )
            self.waveform_selector.param.watch(self.selector.on_select, "value")
            self.selector.param.watch(self.sync_waveforms, "selection")
            self.selector.param.watch(
                self._update_disabled_style, "disable_unplottable"
            )
            # Reactive expression which is True if there are waveforms in this group:
            self.has_waveforms = self.waveform_selector.param.options.rx.bool()
            self._update_disabled_style()

        self.button_row = OptionsButtonRow(selector.main_gui, self)
        # Sub-groups
        self.selection_groups = {
            group.name: SelectionGroup(self.selector, group, self.path + [group.name])
            for group in self.group.groups.values()
        }
        self.accordion = pn.Accordion(
            *self.selection_groups.values(),
            sizing_mode="stretch_width",
        )

        # Create container
        if self.is_root:
            elems = [self.button_row, self.accordion]
        else:
            elems = [self.button_row, self.waveform_selector, self.accordion]
        self.panel = pn.Column(
            *elems, sizing_mode="stretch_width", name=name, visible=self.param.visible
        )

    def sync_waveforms(self, event=None):
        """Update waveform selector options and selected values"""
        new_waveforms = list(self.group.waveforms.keys())
        self.waveform_selector.options = new_waveforms
        self.waveform_selector.value = [
            val for val in new_waveforms if val in self.selector.selection
        ]
        self._update_disabled_style()

    def _update_disabled_style(self, event=None):
        """Grey out the buttons for waveforms that can't be plotted"""
        if not self.selector.disable_unplottable:
            self.waveform_selector.stylesheets = [_BASE_STYLESHEET]
            return
        rules = [_BASE_STYLESHEET]
        for i, name in enumerate(self.waveform_selector.options):
            if not self.group.waveforms[name].is_time_trace:
                rules.append(
                    f"button:nth-of-type({i + 1}) "
                    "{ opacity: 0.35; pointer-events: none; }"
                )
        self.waveform_selector.stylesheets = rules

    def add_group(self, group: WaveformGroup) -> None:
        """Add a sub-group to this UI element."""
        group_ui = SelectionGroup(self.selector, group, self.path + [group.name])
        self.selection_groups[group.name] = group_ui
        self.accordion.append(group_ui)
        # Auto-expand new group. N.B. active list must be replaced to take effect:
        new_index = len(self.accordion.objects) - 1
        self.accordion.active = self.accordion.active + [new_index]

    def remove_group(self, group: str) -> None:
        """Remove a group from this UI element"""
        # Find index of the group UI:
        for index, group_ui in enumerate(self.selection_groups.values()):  # noqa: B007
            if group_ui.name == group:
                break
        # Calculate which panes should be active after removing this one
        new_active = [
            num if num < index else num - 1
            for num in self.accordion.active
            if num != index
        ]
        # Remove from accordion and update active panes
        self.selection_groups.pop(group)
        self.accordion.remove(self.accordion[index])
        self.accordion.active = new_active

    def get_selection(self, recursive=False) -> list[str]:
        """Get a list of the selected waveforms.

        Args:
            recursive: Include selection in sub-groups as well.
        """
        selection = [] if self.is_root else self.waveform_selector.value.copy()
        if recursive:
            for group_ui in self.selection_groups.values():
                selection.extend(group_ui.get_selection(recursive))
        return selection

    def set_selection(self, selection: list[str]) -> None:
        """Select a list of waveforms.

        Args:
            selection: List of waveform names to select.
        """
        if self.waveform_selector is not None:
            self.waveform_selector.value = [
                s for s in selection if s in self.waveform_selector.options
            ]

    def deselect_all(self, event=None) -> None:
        """Deselect all waveforms."""
        self.waveform_selector.value = []

    def select_all(self, event=None) -> None:
        """Select all waveforms, excluding ones that can't be visualized"""
        options = list(self.waveform_selector.options)
        if self.selector.disable_unplottable:
            options = [o for o in options if self.group.waveforms[o].is_time_trace]
        self.waveform_selector.value = options

    def __panel__(self):
        return self.panel
