from typing import TYPE_CHECKING, Union

import panel as pn
from panel.viewable import Viewer

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.group import WaveformGroup
from waveform_editor.gui.selector.options_button_row import OptionsButtonRow

if TYPE_CHECKING:
    from waveform_editor.gui.selector.selector import WaveformSelector


class SelectionGroup(Viewer):
    """User Interface for selecting waveforms in a single waveform group"""

    def __init__(
        self,
        selector: "WaveformSelector",
        group: Union[WaveformConfiguration, WaveformGroup],
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
                stylesheets=["button {text-align: left!important;}"],
            )
            self.waveform_selector.param.watch(self.selector.on_select, "value")
            self.selector.param.watch(self.sync_waveforms, "selection")
            # Reactive expression which is True if there are waveforms in this group:
            self.has_waveforms = self.waveform_selector.param.options.rx.bool()

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
        self.panel = pn.Column(*elems, sizing_mode="stretch_both", name=name)

    def sync_waveforms(self, event=None):
        """Update waveform selector options and selected values"""
        new_waveforms = list(self.group.waveforms.keys())
        self.waveform_selector.options = new_waveforms
        self.waveform_selector.value = [
            val for val in new_waveforms if val in self.selector.selection
        ]

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

    def deselect_all(self, event=None) -> None:
        """Deselect all waveforms."""
        self.waveform_selector.value = []

    def select_all(self, event=None) -> None:
        """Select all waveforms."""
        self.waveform_selector.value = self.waveform_selector.options.copy()

    def __panel__(self):
        return self.panel
