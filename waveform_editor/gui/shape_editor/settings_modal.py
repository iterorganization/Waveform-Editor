import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.nice_plotter import NicePlotter
from waveform_editor.gui.util import WarningIndicator
from waveform_editor.settings import NiceSettings, settings


class SettingsModal(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)

    def __init__(self, nice_plotter: NicePlotter, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice
        self.nice_plotter = nice_plotter

        self.cogwheel_button = pn.widgets.ButtonIcon(
            icon=pn.bind(
                lambda ready: "settings" if ready else "settings-exclamation",
                self.nice_settings.param.are_required_filled,
            ),
            description="Setting Menu",
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

        md_attrs = ["md_pf_active", "md_pf_passive", "md_wall", "md_iron_core"]
        self._md_inputs = {}
        for attr in md_attrs:
            md = getattr(self.nice_settings, attr)
            self._md_inputs[attr] = pn.widgets.TextInput.from_param(md.param.uri)

        machine_preset_content = pn.Column(
            self._preset_selector,
            pn.layout.Divider(),
            pn.Column(
                *(
                    pn.Row(
                        self._md_inputs[attr],
                        WarningIndicator(
                            visible=getattr(
                                self.nice_settings, attr
                            ).param.loaded.rx.not_()
                        ),
                    )
                    for attr in md_attrs
                ),
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
            pn.Row(
                pn.Param(self.nice_settings.param.inv_executable),
                WarningIndicator(
                    visible=self.nice_settings.param.inv_executable.rx() == ""
                ),
            ),
            pn.Row(
                pn.Param(self.nice_settings.param.dir_executable),
                WarningIndicator(
                    visible=self.nice_settings.param.dir_executable.rx() == ""
                ),
            ),
            pn.Param(self.nice_settings.param.environment),
            pn.Param(self.nice_settings.param.verbose),
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
