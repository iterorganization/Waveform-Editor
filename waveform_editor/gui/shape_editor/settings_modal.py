import importlib.resources
import xml.etree.ElementTree as ET

import pandas as pd
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.nice_plotter import NicePlotter
from waveform_editor.gui.util import STYLES, WarningIndicator
from waveform_editor.settings import NiceSettings, settings


class SettingsModal(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)
    MODAL_WIDTH = 700
    MODAL_HEIGHT = 800
    LABEL_WIDTH = 180
    PRESET_WIDTH = 200
    NICE_PARAM_COL_NAME = "Parameter"
    NICE_PARAM_COL_VALUE = "Value"
    NICE_PARAM_COL_DEFAULT = "Default"
    NICE_PARAM_NAME_WIDTH = 240
    NICE_PARAM_DEFAULT_WIDTH = 180
    NICE_PARAM_PAGE_SIZE = 8
    RESET_BUTTON_WIDTH = 180

    def _section_label(self, text):
        return pn.pane.HTML(
            f'<p class="settings-section-label">{text}</p>',
            stylesheets=STYLES,
            margin=0,
            sizing_mode="stretch_width",
        )

    def _settings_section(self, *items):
        return pn.Column(
            *items,
            stylesheets=STYLES,
            css_classes=["settings-card"],
            sizing_mode="stretch_width",
        )

    def _form_row(self, label, widget, warning=None):
        items = [
            pn.pane.HTML(
                f'<span class="form-row-label">{label}</span>',
                stylesheets=STYLES,
                width=self.LABEL_WIDTH,
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

    def __init__(self, nice_plotter: NicePlotter, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice
        self.nice_plotter = nice_plotter

        modal = self._build_modal()
        button_icon = pn.widgets.ButtonIcon(
            icon=pn.bind(
                lambda ready: "settings" if ready else "settings-exclamation",
                self.nice_settings.param.are_required_filled,
            ),
            active_icon="settings-filled",
            description="Setting Menu",
            size="24px",
            margin=(15, 10, 2, 10),
            on_click=lambda event: modal.show(),
        )
        self.panel = pn.Row(button_icon, modal)

        self.nice_settings.param.watch(
            self._update_md_inputs_visibility, ["machine_preset"]
        )
        self._update_md_inputs_visibility(None)

    def _parameters_section(self):
        """A table of every NICE parameter, which writes edits to the settings."""
        parameters = ET.fromstring(
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("param.xml")
            .read_text()
        )
        self._defaults = {p.tag: (p.text or "").strip() for p in parameters}
        self.parameter_table = pn.widgets.Tabulator(
            self._parameter_frame(),
            show_index=False,
            header_filters=True,
            editors={
                self.NICE_PARAM_COL_NAME: None,
                self.NICE_PARAM_COL_VALUE: {"type": "input"},
                self.NICE_PARAM_COL_DEFAULT: None,
            },
            widths={
                self.NICE_PARAM_COL_NAME: self.NICE_PARAM_NAME_WIDTH,
                self.NICE_PARAM_COL_DEFAULT: self.NICE_PARAM_DEFAULT_WIDTH,
            },
            sizing_mode="stretch_width",
            # Paged rather than scrolled, so the table does not put a second
            # scrollbar inside the one of the settings tab
            pagination="local",
            page_size=self.NICE_PARAM_PAGE_SIZE,
            on_edit=self._on_parameter_edit,
        )
        reset = pn.widgets.Button(
            name="Reset all to defaults",
            width=self.RESET_BUTTON_WIDTH,
            on_click=self._reset_parameters,
        )
        return pn.Column(
            self._section_label("NICE parameters"),
            self._settings_section(self.parameter_table, reset),
            sizing_mode="stretch_width",
        )

    def _parameter_frame(self):
        """The table contents: each parameter, its value and its default."""
        overrides = self.nice_settings.xml_parameters
        return pd.DataFrame(
            [
                {
                    self.NICE_PARAM_COL_NAME: name,
                    self.NICE_PARAM_COL_VALUE: str(overrides.get(name, default)),
                    self.NICE_PARAM_COL_DEFAULT: default,
                }
                for name, default in self._defaults.items()
            ]
        )

    def _reset_parameters(self, event=None):
        """Put every parameter back to the value NICE is shipped with."""
        self.nice_settings.xml_parameters = {}
        self.parameter_table.value = self._parameter_frame()

    def _on_parameter_edit(self, event):
        """Keep an edited parameter in the settings, unless it is back to default."""
        row = self.parameter_table.value.iloc[event.row]
        name = row[self.NICE_PARAM_COL_NAME]
        overrides = dict(self.nice_settings.xml_parameters)
        value = str(event.value).strip()
        if value == row[self.NICE_PARAM_COL_DEFAULT]:
            overrides.pop(name, None)
        else:
            overrides[name] = value
        self.nice_settings.xml_parameters = overrides

    def _build_modal(self):
        # Inputs for machine description URIs
        self._md_inputs = {}

        # --- Machine Presets tab ---
        preset_selector = pn.widgets.Select.from_param(
            self.nice_settings.param.machine_preset, name="", width=self.PRESET_WIDTH
        )
        md_rows = []
        for md in self.nice_settings.machine_descriptions:
            self._md_inputs[md] = pn.widgets.TextInput.from_param(md.param.uri, name="")
            md_rows.append(
                self._form_row(
                    md.ids_name,
                    self._md_inputs[md],
                    WarningIndicator(margin=10, visible=md.param.loaded.rx.not_()),
                )
            )
        machine_preset_content = pn.Column(
            self._section_label("Preset"),
            preset_selector,
            self._section_label("Machine Description URIs"),
            self._settings_section(*md_rows),
            sizing_mode="stretch_width",
            scroll=True,
        )

        # --- Display tab ---
        self._contour_detail = pn.Column(
            self._section_label("Contour Detail"),
            self._settings_section(
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
            self._section_label("Visibility"),
            self._settings_section(
                pn.Param(
                    self.nice_plotter.param,
                    parameters=[
                        "show_contour",
                        "show_coils",
                        "show_wall",
                        "show_vacuum_vessel",
                        "show_passive_structures",
                        "show_iron_core",
                        "show_components",
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
            self._section_label("Executables"),
            self._settings_section(
                self._form_row(
                    "Inverse executable",
                    pn.widgets.TextInput.from_param(
                        self.nice_settings.param.inv_executable, name=""
                    ),
                    WarningIndicator(
                        margin=10,
                        visible=self.nice_settings.param.inv_executable.rx() == "",
                    ),
                ),
                self._form_row(
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
            self._section_label("Environment"),
            self._settings_section(
                self._form_row(
                    "Environment variables",
                    pn.Param(self.nice_settings.param.environment, show_name=False),
                ),
            ),
            self._parameters_section(),
            sizing_mode="stretch_width",
            scroll=True,
        )

        self.tabs = pn.Tabs(
            ("Display", display_content),
            ("Machine Presets", machine_preset_content),
            ("NICE Configuration", nice_content),
            margin=(20, 20, 0, 20),
            sizing_mode="stretch_width",
            stylesheets=STYLES,
        )

        return pn.Modal(
            self.tabs,
            width=self.MODAL_WIDTH,
            height=self.MODAL_HEIGHT,
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
