import json

import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.nice_plotter import NicePlotter
from waveform_editor.settings import NiceSettings, settings


class SettingsModal(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)

    def __init__(self, nice_plotter: NicePlotter, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice
        self.nice_plotter = nice_plotter

        self.cogwheel_button = pn.widgets.ButtonIcon(
            icon="settings",
            size="30px",
            on_click=self._open_modal,
        )

        self._build_modal()
        self._setup_preset_watcher()

    def _build_modal(self):
        self._preset_selector = pn.widgets.Select.from_param(
            self.nice_settings.param.machine_preset,
            width=200,
        )

        md_params = ["md_pf_active", "md_pf_passive", "md_wall", "md_iron_core"]
        self._md_inputs = {}
        for p in md_params:
            self._md_inputs[p] = pn.widgets.TextInput.from_param(
                self.nice_settings.param[p],
            )

        machine_preset_content = pn.Column(
            self._preset_selector,
            pn.layout.Divider(),
            pn.Column(
                *(self._md_inputs[p] for p in md_params),
            ),
            sizing_mode="stretch_width",
        )

        general_content = pn.Column(
            pn.pane.Markdown("*No general settings yet.*"),
        )

        display_content = pn.Column(
            pn.Param(
                self.nice_plotter.param,
                parameters=[
                    "show_contour",
                    "levels",
                    "show_coils",
                    "show_wall",
                    "show_vacuum_vessel",
                    "show_xo",
                    "show_separatrix",
                    "show_desired_shape",
                ],
                show_name=False,
                widgets={
                    "show_desired_shape": {
                        "visible": self.nice_settings.param.is_inverse_mode
                    }
                },
            ),
        )

        nice_content = pn.Column(
            pn.Param(
                self.nice_settings.param.inv_executable,
                width=300,
            ),
            pn.Param(
                self.nice_settings.param.dir_executable,
                width=300,
            ),
            pn.Param(
                self.nice_settings.param.environment,
                width=300,
            ),
            pn.Param(
                self.nice_settings.param.verbose,
                width=100,
            ),
        )

        self.tabs = pn.Tabs(
            ("Machine Presets", machine_preset_content),
            ("General", general_content),
            ("Display", display_content),
            ("NICE Configuration", nice_content),
            width=600,
            height=400,
        )

        self.modal = pn.Modal(
            self.tabs,
            width=650,
            height=500,
        )

    def _setup_preset_watcher(self):
        def update_md_inputs_visibility(event):
            is_custom = (
                self.nice_settings.machine_preset == self.nice_settings.PRESET_CUSTOM
            )
            for inp in self._md_inputs.values():
                inp.disabled = not is_custom

        self.nice_settings.param.watch(update_md_inputs_visibility, ["machine_preset"])
        update_md_inputs_visibility(None)

    def _open_modal(self, event):
        self.modal.show()

    def _close_modal(self, event):
        self.modal.hide()

    def __panel__(self):
        return pn.Row(self.cogwheel_button, self.modal)
