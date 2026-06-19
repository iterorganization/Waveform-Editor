import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.nice_plotter import NicePlotter
from waveform_editor.gui.util import STYLES, WarningIndicator
from waveform_editor.settings import NiceSettings, settings


def _section_label(text):
    return pn.pane.HTML(
        f'<p class="settings-section-label">{text}</p>',
        stylesheets=STYLES,
        margin=0,
        sizing_mode="stretch_width",
    )


def _settings_section(*items):
    return pn.Column(
        *items,
        stylesheets=STYLES,
        css_classes=["settings-card"],
        sizing_mode="stretch_width",
    )


def _form_row(label, widget, warning=None):
    items = [
        pn.pane.HTML(
            f'<span class="form-row-label">{label}</span>',
            stylesheets=STYLES,
            width=180,
            align="center",
        ),
        widget,
    ]
    if warning is not None:
        items.append(warning)
    return pn.Row(
        *items,
        css_classes=["form-row"],
        stylesheets=STYLES,
        sizing_mode="stretch_width",
        align="center",
    )


class SettingsModal(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)

    def __init__(self, nice_plotter: NicePlotter, shape_editor, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice
        self.nice_plotter = nice_plotter
        self._shape_editor = shape_editor

        modal = self._build_modal()
        button_icon = pn.widgets.ButtonIcon(
            icon=pn.bind(
                lambda ready: "settings" if ready else "settings-exclamation",
                self.nice_settings.param.are_required_filled,
            ),
            active_icon="settings-filled",
            description="Setting Menu",
            size="30px",
            on_click=lambda event: modal.show(),
        )
        self.panel = pn.Row(button_icon, modal)

        self.nice_settings.param.watch(
            self._update_md_inputs_visibility, ["machine_preset"]
        )

    def _build_modal(self):
        # Inputs for machine description URIs
        self._md_inputs = {}

        # --- Machine Presets tab ---
        preset_selector = pn.widgets.Select.from_param(
            self.nice_settings.param.machine_preset, name="", width=200
        )
        md_rows = []
        for md in self.nice_settings.machine_descriptions:
            self._md_inputs[md] = pn.widgets.TextInput.from_param(md.param.uri, name="")
            md_rows.append(
                _form_row(
                    md.ids_name,
                    self._md_inputs[md],
                    WarningIndicator(margin=10, visible=md.param.loaded.rx.not_()),
                )
            )
        machine_preset_content = pn.Column(
            _section_label("Preset"),
            preset_selector,
            _section_label("Machine Description URIs"),
            _settings_section(*md_rows),
            sizing_mode="stretch_width",
            scroll=True,
        )

        # --- Display tab ---
        self._contour_detail = pn.Column(
            _section_label("Contour Detail"),
            _settings_section(
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
            _settings_section(
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
                            "visible": self.nice_settings.param.is_inverse_mode.rx()
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
            _settings_section(
                _form_row(
                    "Inverse executable",
                    pn.widgets.TextInput.from_param(
                        self.nice_settings.param.inv_executable, name=""
                    ),
                    WarningIndicator(
                        margin=10,
                        visible=self.nice_settings.param.inv_executable.rx() == "",
                    ),
                ),
                _form_row(
                    "Direct executable",
                    pn.widgets.TextInput.from_param(
                        self.nice_settings.param.dir_executable, name=""
                    ),
                    WarningIndicator(
                        margin=10,
                        visible=self.nice_settings.param.dir_executable.rx() == "",
                    ),
                ),
            ),
            _section_label("Environment"),
            _settings_section(
                _form_row(
                    "Environment variables",
                    pn.Param(self.nice_settings.param.environment, show_name=False),
                ),
                _form_row(
                    "Verbosity",
                    pn.Param(self.nice_settings.param.verbose, show_name=False),
                ),
            ),
            sizing_mode="stretch_width",
            scroll=True,
        )

        # --- General tab ---
        self._warm_start_switch = pn.widgets.Switch.from_param(
            self._shape_editor.param.use_previous_run,
            name="",
            disabled=self._shape_editor.communicator.param.can_warm_start.rx.not_(),
            margin=(15, 0, 0, 0),
        )
        no_equilibrium_msg = pn.pane.HTML(
            '<span class="form-row-label form-row-label--warning">'
            "No previous equilibrium available, run NICE to enable."
            "</span>",
            stylesheets=STYLES,
            visible=self._shape_editor.communicator.param.can_warm_start.rx.not_(),
            sizing_mode="stretch_width",
            margin=(4, 10),
        )
        general_content = pn.Column(
            _section_label("Warm Start"),
            _settings_section(
                _form_row(
                    "Start from previous equilibrium",
                    self._warm_start_switch,
                    pn.widgets.TooltipIcon(
                        value=(
                            "Use the previous converged equilibrium as the starting "
                            "point. Disabled when no valid equilibrium is available."
                        ),
                        margin=10,
                    ),
                ),
                no_equilibrium_msg,
            ),
            sizing_mode="stretch_width",
            scroll=True,
        )

        self.tabs = pn.Tabs(
            ("Display", display_content),
            ("General", general_content),
            ("Machine Presets", machine_preset_content),
            ("NICE Configuration", nice_content),
            margin=(20, 20, 0, 20),
            sizing_mode="stretch_width",
            stylesheets=STYLES,
        )

        return pn.Modal(
            self.tabs,
            width=700,
            height=560,
            stylesheets=STYLES,
        )

    def _update_md_inputs_visibility(self, _):
        """Disable machine description URI inputs if preset is selected."""
        for inp in self._md_inputs.values():
            inp.disabled = (
                self.nice_settings.machine_preset != self.nice_settings.PRESET_CUSTOM
            )

    def __panel__(self):
        return self.panel
