from typing import TYPE_CHECKING

import panel as pn
from panel.viewable import Viewer

from waveform_editor.gui.selector.text_input_form import TextInputForm

if TYPE_CHECKING:
    from waveform_editor.gui.main import WaveformEditorGui
    from waveform_editor.gui.selector.selector import WaveformSelector


class OptionsButtonRow(Viewer):
    """Row of options buttons for waveform/group management.

    Operates on the currently active group tracked by selector.active_group_path.
    """

    def __init__(self, main_gui: "WaveformEditorGui", selector: "WaveformSelector"):
        super().__init__()
        self.main_gui = main_gui
        self.config = main_gui.config
        self.selector = selector

        not_root = pn.bind(lambda path: bool(path), selector.param.active_group_path)

        self.select_all_button = pn.widgets.ButtonIcon(
            icon="select-all",
            size="20px",
            active_icon="check",
            description="Select all waveforms in active group",
            on_click=self._select_all,
            disabled=selector.param.multiselect.rx.not_(),
        )
        self.deselect_all_button = pn.widgets.ButtonIcon(
            icon="deselect",
            size="20px",
            active_icon="check",
            description="Deselect all waveforms in active group",
            on_click=self._deselect_all,
        )
        self.new_waveform_button = pn.widgets.ButtonIcon(
            icon="plus",
            size="20px",
            active_icon="check",
            description="Add new waveform to active group",
            on_click=self._on_add_waveform_button_click,
            visible=not_root,
        )
        self.new_waveform_panel = TextInputForm(
            "Enter name of new waveform",
            is_visible=False,
            on_click=self._add_new_waveform,
        )
        self.remove_waveform_button = pn.widgets.ButtonIcon(
            icon="minus",
            size="20px",
            active_icon="check",
            description="Remove selected waveforms from active group",
            on_click=self._show_remove_waveform_modal,
            visible=not_root,
        )
        self.rename_waveform_button = pn.widgets.ButtonIcon(
            icon="cursor-text",
            size="20px",
            active_icon="check",
            description="Rename selected waveform",
            on_click=self._on_rename_waveform_button_click,
        )
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
        self.remove_group_button = pn.widgets.ButtonIcon(
            icon="trash",
            size="20px",
            active_icon="trash-filled",
            description="Remove active group",
            on_click=self._show_remove_group_modal,
            visible=not_root,
        )

        option_buttons = pn.Row(
            self.new_waveform_button,
            self.remove_waveform_button,
            self.new_group_button,
            self.select_all_button,
            self.deselect_all_button,
            self.remove_group_button,
            self.rename_waveform_button,
        )
        self.panel = pn.Column(
            option_buttons,
            self.new_waveform_panel,
            self.new_group_panel,
        )

    def _get_active_group(self):
        group = self.config
        for part in self.selector.active_group_path:
            group = group.groups[part]
        return group

    def _get_active_group_selection(self):
        """Selected waveforms that belong to the active group."""
        path = self.selector.active_group_path
        if not path:
            return []
        group = self._get_active_group()
        return [w for w in self.selector.selection if w in group.waveforms]

    def _select_all(self, event=None):
        path = self.selector.active_group_path
        if not path:
            pn.state.notifications.warning("Click a group in the tree first.")
            return
        all_wf = list(self._get_active_group().waveforms.keys())
        new_sel = list(dict.fromkeys(self.selector.selection + all_wf))
        self.selector.set_selection(new_sel)

    def _deselect_all(self, event=None):
        path = self.selector.active_group_path
        if not path:
            return
        grp_wf = set(self._get_active_group().waveforms.keys())
        new_sel = [w for w in self.selector.selection if w not in grp_wf]
        self.selector.set_selection(new_sel)

    def _show_remove_waveform_modal(self, event):
        selection = self._get_active_group_selection()
        if not selection:
            pn.state.notifications.error("No waveforms selected for removal.")
            return
        path = self.selector.active_group_path
        self.main_gui.confirm_modal.show(
            f"Are you sure you want to delete the selected waveform(s) from the "
            f"**{path[-1]}** group?",
            on_confirm=self._remove_waveforms,
        )

    def _remove_waveforms(self):
        for waveform_name in self._get_active_group_selection():
            self.config.remove_waveform(waveform_name)
        with self.selector.is_removing_waveform:
            new_sel = [
                v for v in self.selector.selection if v in self.config.waveform_map
            ]
            self.selector._rebuild_tree()
            self.selector.set_selection(new_sel)

    def _show_remove_group_modal(self, event):
        path = self.selector.active_group_path
        if not path:
            return
        self.main_gui.confirm_modal.show(
            f"Are you sure you want to delete the **{path[-1]}** group?  \n"
            "This will also remove all waveforms and subgroups in this group!",
            on_confirm=self._remove_group,
        )

    def _remove_group(self):
        path = self.selector.active_group_path
        self.config.remove_group(path)
        self.selector.remove_group(path)

    def _on_add_waveform_button_click(self, event):
        self.new_waveform_panel.is_visible(True)

    def _add_new_waveform(self, event):
        name = self.new_waveform_panel.input.value_input
        path = self.selector.active_group_path
        new_waveform = self.config.parse_waveform(f"{name}:\n- {{}}")
        self.config.add_waveform(new_waveform, path)
        self.selector._rebuild_tree()
        self.new_waveform_panel.cancel()

    def _on_add_group_button_click(self, event):
        self.new_group_panel.is_visible(True)

    def _on_rename_waveform_button_click(self, event):
        selection = self.selector.selection
        if len(selection) != 1:
            pn.state.notifications.error(
                "You must select only a single waveform to rename."
            )
            return
        self.main_gui.rename_modal.show(
            current_name=selection[0], on_accept=self._rename_waveform
        )

    def _rename_waveform(self, new_name):
        old_name = self.selector.selection[0]
        if new_name == old_name:
            return
        self.config.rename_waveform(old_name, new_name)
        self.selector._rebuild_tree()
        self.selector.set_selection([new_name])

    def _add_new_group(self, event):
        name = self.new_group_panel.input.value_input
        path = self.selector.active_group_path
        new_group = self.config.add_group(name, path)
        self.selector.active_group_path = path + [new_group.name]
        self.selector._rebuild_tree()
        self.new_group_panel.cancel()

    def __panel__(self):
        return self.panel
