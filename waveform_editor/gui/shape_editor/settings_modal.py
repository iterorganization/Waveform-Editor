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
    # Shares of the table width, so that the columns fill it
    NICE_PARAM_NAME_WIDTH = "40%"
    NICE_PARAM_VALUE_WIDTH = "30%"
    NICE_PARAM_DEFAULT_WIDTH = "30%"
    NICE_PARAM_PAGE_SIZE = 8
    RESET_BUTTON_WIDTH = 180

    def _section_label(self, text):
        """A heading above a section."""
        return pn.pane.HTML(
            f'<p class="settings-section-label">{text}</p>',
            stylesheets=STYLES,
            margin=0,
            sizing_mode="stretch_width",
        )

    def _settings_section(self, *items):
        """A card holding the settings of a section."""
        return pn.Column(
            *items,
            stylesheets=STYLES,
            css_classes=["settings-card"],
            sizing_mode="stretch_width",
        )

    def _form_row(self, label, widget, warning=None):
        """A labelled input, with an optional warning next to it."""
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
                self.NICE_PARAM_COL_VALUE: self.NICE_PARAM_VALUE_WIDTH,
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
        """Creates the modal, with a tab per kind of setting."""
        self.tabs = pn.Tabs(
            ("Display", self._display_tab()),
            ("Machine Presets", self._machine_presets_tab()),
            ("NICE Configuration", self._nice_tab()),
            margin=(20, 20, 0, 20),
            width=self.MODAL_WIDTH,
            height=self.MODAL_HEIGHT,
            stylesheets=STYLES,
        )
        return pn.Modal(self.tabs, stylesheets=STYLES)

    def _tab(self, *items):
        """A scrollable tab."""
        return pn.Column(*items, sizing_mode="stretch_width", scroll=True)

    def _display_tab(self):
        """Show display settings."""
        plotter = self.nice_plotter.display_settings.param
        is_inverse = self.nice_settings.param.is_inverse_mode.rx()
        return self._tab(
            self._section_label("Poloidal Flux"),
            self._settings_section(
                self._display_inputs("show_contour"),
                self._options(
                    self._display_inputs("levels"), visible=plotter.show_contour
                ),
                self._display_inputs("show_heatmap"),
                self._options(
                    self._display_inputs("heatmap_alpha"), visible=plotter.show_heatmap
                ),
                self._display_inputs("show_colorbar"),
            ),
            self._section_label("Machine"),
            self._settings_section(
                self._display_inputs(
                    "show_coils",
                    "show_wall",
                    "show_vacuum_vessel",
                    "show_passive_structures",
                    "show_iron_core",
                    "show_plasma_facing_components",
                )
            ),
            self._section_label("Result"),
            self._settings_section(
                self._display_inputs(
                    "show_separatrix",
                    "show_xo",
                    "show_strike_points",
                    "show_result_gaps",
                )
            ),
            self._section_label("Target"),
            self._settings_section(
                pn.Column(
                    pn.widgets.Checkbox.from_param(
                        plotter.show_target_shape, visible=is_inverse
                    ),
                    self.nice_plotter.plasma_shape.reference.show_input(),
                    pn.widgets.Checkbox.from_param(
                        plotter.show_target_gaps, visible=is_inverse
                    ),
                    margin=(5, 10),
                ),
            ),
        )

    def _display_inputs(self, *names):
        """The inputs of display settings."""
        return pn.Param(
            self.nice_plotter.display_settings.param,
            parameters=list(names),
            show_name=False,
        )

    def _options(self, *items, visible):
        """Options of a toggle, nested under it and only there while it is on."""
        return pn.Column(
            *items,
            visible=visible,
            styles={"border-left": "2px solid #dee2e6", "padding-left": "8px"},
            margin=(0, 0, 4, 22),
        )

    def _machine_presets_tab(self):
        """The cluster, machine preset and machine description URIs."""
        self._md_inputs = {}
        md_rows = {True: [], False: []}
        for md in self.nice_settings.machine_descriptions:
            self._md_inputs[md] = pn.widgets.TextInput.from_param(md.param.uri, name="")
            not_loaded = md.param.loaded.rx.not_()
            if not md.required:
                # An optional machine description may be left empty
                not_loaded = not_loaded & md.param.uri.rx.bool()
            md_rows[md.required].append(
                self._form_row(
                    md.ids_name,
                    self._md_inputs[md],
                    WarningIndicator(margin=10, visible=not_loaded),
                )
            )
        return self._tab(
            self._section_label("Cluster"),
            pn.widgets.Select.from_param(
                self.nice_settings.param.cluster, name="", width=self.PRESET_WIDTH
            ),
            pn.Column(
                self._section_label("Machine Preset"),
                pn.widgets.Select.from_param(
                    self.nice_settings.param.machine_preset,
                    name="",
                    width=self.PRESET_WIDTH,
                ),
                visible=self.nice_settings.param.cluster.rx()
                != self.nice_settings.CUSTOM,
            ),
            self._section_label("Required Machine Descriptions"),
            self._settings_section(*md_rows[True]),
            self._section_label("Optional Machine Descriptions"),
            self._settings_section(*md_rows[False]),
        )

    def _nice_tab(self):
        """The NICE executables, environment and parameters."""
        return self._tab(
            self._section_label("Executables"),
            self._settings_section(
                self._executable_row(
                    "Inverse executable", self.nice_settings.param.inv_executable
                ),
                self._executable_row(
                    "Direct executable", self.nice_settings.param.dir_executable
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
        )

    def _executable_row(self, label, parameter):
        """An executable path, with a warning while it is empty."""
        return self._form_row(
            label,
            pn.widgets.TextInput.from_param(parameter, name=""),
            WarningIndicator(margin=10, visible=parameter.rx() == ""),
        )

    def _update_md_inputs_visibility(self, _):
        """Disable machine description URI inputs if preset is selected."""
        for inp in self._md_inputs.values():
            inp.disabled = (
                self.nice_settings.machine_preset != self.nice_settings.CUSTOM
            )

    def __panel__(self):
        return self.panel
