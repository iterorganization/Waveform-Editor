import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.nice_plotter import NicePlotter
from waveform_editor.gui.util import WarningIndicator
from waveform_editor.settings import NiceSettings, settings

_CARD_STYLES = {
    "background": "rgba(255,255,255,0.04)",
    "border": "1px solid rgba(255,255,255,0.1)",
    "border-radius": "8px",
    "overflow": "hidden",
}


def _section_label(text):
    return pn.pane.HTML(
        f'<p style="color:#999;font-size:11px;font-weight:600;'
        f'letter-spacing:0.08em;text-transform:uppercase;margin:14px 0 5px 0;">'
        f"{text}</p>",
        margin=0,
        sizing_mode="stretch_width",
    )


def _card(*items):
    return pn.Column(*items, styles=_CARD_STYLES, sizing_mode="stretch_width")


class SettingsModal(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)

    def __init__(self, nice_plotter: NicePlotter, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice
        self.nice_plotter = nice_plotter

        self.modal = self._build_modal()
        self.nice_settings.param.watch(
            self._update_md_inputs_visibility, ["machine_preset"]
        )

        self.panel = pn.widgets.ButtonIcon(
            icon=pn.bind(
                lambda ready: "settings" if ready else "settings-exclamation",
                self.nice_settings.param.are_required_filled,
            ),
            active_icon="settings-filled",
            description="Setting Menu",
            size="30px",
            on_click=self._open_modal,
        )

    def _build_modal(self):
        self._md_inputs = {}

        # --- Machine Presets tab ---
        preset_selector = pn.widgets.Select.from_param(
            self.nice_settings.param.machine_preset, name="", width=200
        )
        md_uris = pn.Column()
        for md in self.nice_settings.mds:
            self._md_inputs[md] = pn.widgets.TextInput.from_param(md.param.uri)
            md_uris.append(
                pn.Row(
                    self._md_inputs[md],
                    WarningIndicator(visible=md.param.loaded.rx.not_()),
                )
            )
        machine_preset_content = pn.Column(
            _section_label("Preset"),
            preset_selector,
            _section_label("Machine Description URIs"),
            md_uris,
            sizing_mode="stretch_width",
            scroll=True,
        )

        # --- General tab ---
        general_content = pn.Column(
            pn.pane.HTML(
                '<p style="color:#888;font-style:italic;'
                'margin-top:24px;text-align:center;">'
                "No general settings yet.</p>"
            ),
        )

        # --- Display tab ---
        self._contour_detail = pn.Column(
            _section_label("Contour Detail"),
            _card(
                pn.Param(
                    self.nice_plotter.param,
                    parameters=["levels"],
                    show_name=False,
                ),
            ),
            visible=self.nice_plotter.show_contour,
            sizing_mode="stretch_width",
        )
        self.nice_plotter.param.watch(
            lambda e: setattr(self._contour_detail, "visible", e.new),
            ["show_contour"],
        )

        display_content = pn.Column(
            _section_label("Visibility"),
            _card(
                pn.Param(
                    self.nice_plotter.param,
                    parameters=[
                        "show_contour",
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
                        },
                    },
                ),
            ),
            self._contour_detail,
            sizing_mode="stretch_width",
            scroll=True,
        )

        # --- NICE Configuration tab ---
        nice_content = pn.Column(
            _section_label("Executables"),
            _card(
                pn.Row(
                    pn.Param(self.nice_settings.param.inv_executable),
                    WarningIndicator(
                        visible=self.nice_settings.param.inv_executable.rx() == ""
                    ),
                    sizing_mode="stretch_width",
                ),
                pn.Row(
                    pn.Param(self.nice_settings.param.dir_executable),
                    WarningIndicator(
                        visible=self.nice_settings.param.dir_executable.rx() == ""
                    ),
                    sizing_mode="stretch_width",
                ),
            ),
            _section_label("Environment"),
            _card(
                pn.Param(self.nice_settings.param.environment),
                pn.Param(self.nice_settings.param.verbose),
            ),
            sizing_mode="stretch_width",
            scroll=True,
        )

        self.tabs = pn.Tabs(
            ("Machine Presets", machine_preset_content),
            ("General", general_content),
            ("Display", display_content),
            ("NICE Configuration", nice_content),
            margin=(20, 20, 0, 20),
            sizing_mode="stretch_width",
            stylesheets=[".bk-tab { flex: 1; text-align: center; }"],
        )

        return pn.Modal(
            self.tabs,
            width=700,
            height=560,
            stylesheets=[
                ".dialog-content { border-radius: 20px; "
                "overflow: hidden; padding: 0 !important; }"
            ],
        )

    def _update_md_inputs_visibility(self, _):
        """Disable machine description URI inputs if preset is selected."""
        for inp in self._md_inputs.values():
            inp.disabled = (
                self.nice_settings.machine_preset != self.nice_settings.PRESET_CUSTOM
            )

    def _open_modal(self, event):
        self.modal.show()

    def _close_modal(self, event):
        self.modal.hide()

    def __panel__(self):
        return pn.Row(self.panel, self.modal)
