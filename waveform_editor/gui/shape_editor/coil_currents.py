import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import panel as pn
import param
from bokeh.models.widgets.tables import NumberFormatter
from panel.viewable import Viewer

from waveform_editor.derived_waveform import DerivedWaveform
from waveform_editor.settings import settings
from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency


class CoilCurrentEntry(param.Parameterized):
    coil_name = param.String()
    fix_current = param.Boolean(default=False)
    current = param.Number(default=None)
    previous_current = param.Number(default=None)
    # TODO: add additional columns for penalization to 0 checkbox and pen. weight


class CoilCurrents(Viewer):
    coils = param.List(doc="List of CoilCurrentEntry for each coil")
    export_time = param.Number(
        doc="Select a time at which coil currents will be saved to waveforms"
    )
    table = param.ClassSelector(class_=pn.widgets.Tabulator, default=None)

    # Table column names
    COIL_NAME = "coil_name"
    FIX_CURRENT = "fix_current"
    CURRENT = "current"
    PREV_CURRENT = "previous_current"

    def __init__(self, main_gui, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice
        self.main_gui = main_gui

        titles = {
            self.COIL_NAME: "Name",
            self.FIX_CURRENT: "Fix",
            self.CURRENT: "Coil current [A]",
            self.PREV_CURRENT: "Previous current [A]",
        }
        header_tooltips = {
            self.COIL_NAME: "The name of the coil",
            self.FIX_CURRENT: "Fix coil current to a specific value.",
            self.CURRENT: "Coil current",
            self.PREV_CURRENT: "Coil current input to previous run of the solver.",
        }
        editors = {
            self.COIL_NAME: None,
            self.FIX_CURRENT: None,
            self.CURRENT: {"type": "number"},
            self.PREV_CURRENT: None,
        }
        formatters = {
            self.FIX_CURRENT: {"type": "tickCross"},
            self.CURRENT: NumberFormatter(),
            self.PREV_CURRENT: NumberFormatter(),
        }
        self.table = pn.widgets.Tabulator(
            layout="fit_data_stretch",
            sizing_mode="stretch_width",
            show_index=False,
            titles=titles,
            editors=editors,
            formatters=formatters,
            header_tooltips=header_tooltips,
            header_align="center",
            text_align="center",
            sortable=False,
            selectable=False,
            visible=self.param.coils.rx.bool(),
            on_edit=self._on_cell_edit,
            on_click=self._on_cell_click,
        )

        self.guide_message = pn.pane.Markdown(
            "_To fix a coil to a specific current, enable the Fix checkbox and provide "
            " the desired current value._",
            visible=self.param.coils.rx.bool(),
            margin=(0, 10),
        )
        self.no_ids_message = pn.pane.Markdown(
            "Please load a valid 'pf_active' IDS in the _NICE Configuration_ settings.",
            visible=self.param.coils.rx.not_(),
        )

        export_time_input = pn.widgets.FloatInput.from_param(self.param.export_time)
        confirm_button = pn.widgets.Button(
            on_click=lambda event: self._store_coil_currents(),
            name="Save Currents as Waveforms",
            margin=(30, 0, 0, 0),
        )
        self.panel = pn.Column(
            pn.Row(
                export_time_input,
                confirm_button,
                visible=self.param.coils.rx.bool(),
            ),
            self.no_ids_message,
            self.guide_message,
            self.table,
        )

    def create_ui(self, pf_active):
        """Create the UI for each coil in the provided pf_active IDS.

        Args:
            pf_active: pf_active IDS containing coils with current values.
        """
        if not pf_active:
            self.coils = []
            return

        new_coils = []
        for coil in pf_active.coil:
            coil_current = coil.current
            entry = CoilCurrentEntry(
                coil_name=str(coil.name),
                current=coil_current.data[0] if coil_current.data.has_value else None,
            )
            new_coils.append(entry)

        self.coils = new_coils

    @param.depends("coils", watch=True)
    def _update_table(self):
        data = []
        for coil in self.coils:
            data.append(
                {
                    self.COIL_NAME: coil.coil_name,
                    self.FIX_CURRENT: coil.fix_current,
                    self.CURRENT: "" if coil.current is None else coil.current,
                    self.PREV_CURRENT: ""
                    if coil.previous_current is None
                    else coil.previous_current,
                }
            )
        self.table.value = pd.DataFrame(data)

    def _on_cell_edit(self, event):
        coil = self.coils[event.row]
        if event.column == self.FIX_CURRENT:
            coil.fix_current = bool(event.value)
        elif event.column == self.CURRENT:
            coil.current = float(event.value)

    def _on_cell_click(self, event):
        coil = self.coils[event.row]
        if event.column == self.FIX_CURRENT:
            coil.fix_current = not coil.fix_current
            self._update_table()

    def _store_coil_currents(self, group_name="Coil Currents"):
        """Store the current values from the coil UI sliders into the waveform
        configuration.

        Args:
            group_name: Name of the group to create new coil current waveforms in if
                they do not already exist.
        """
        coil_currents = [c.current for c in self.coils]
        config = self.main_gui.config
        new_waveforms_created = False

        if not self._has_valid_export_time():
            return

        for i, current in enumerate(coil_currents):
            name = f"pf_active/coil({i + 1})/current/data"
            if name not in config.waveform_map:
                if group_name not in config.groups:
                    config.add_group(group_name, [])
                self._create_new_waveform(config, name, current, group_name)
                new_waveforms_created = True
            else:
                waveform = config[name]
                if isinstance(waveform, DerivedWaveform):
                    pn.state.notifications.error(
                        f"Could not store coil current in waveform {name!r}, "
                        "because it is a derived waveform"
                    )
                    continue
                self._append_to_existing_waveform(config, name, current)

        if new_waveforms_created:
            self.main_gui.selector.refresh()
            pn.state.notifications.success(
                f"New waveform(s) were added in the {group_name!r} group"
            )
        else:
            pn.state.notifications.success(
                "The values of the coil currents were appended to their respective "
                "waveforms."
            )

    def _append_to_existing_waveform(self, config, name, current):
        """Append coil current value to an existing waveform. If the last tendency is a
        piecewise tendency, it is extended, otherwise a new piecewise tendency
        is added.

        Args:
            config: The waveform configuration.
            name: Name of the waveform.
            current: Coil current value to append.
        """
        waveform = config[name]
        last_tendency = waveform.tendencies[-1]

        # Either append to existing piecewise linear tendency, or create new
        # piecewise linear tendency
        if isinstance(last_tendency, PiecewiseLinearTendency):
            waveform.yaml[-1]["time"].append(float(self.export_time))
            waveform.yaml[-1]["value"].append(float(current))
            yaml_str = f"{name}:\n{waveform.get_yaml_string()}"
        else:
            end = waveform.tendencies[-1].end
            new_piecewise = (
                f"- {{type: piecewise, time: [{end}, {self.export_time}], "
                f"value: [{current}, {current}]}}"
            )
            yaml_str = f"{name}:\n{waveform.get_yaml_string()}{new_piecewise}"

        new_waveform = config.parse_waveform(yaml_str)
        config.replace_waveform(new_waveform)

    def _create_new_waveform(self, config, name, current, group_name):
        """Create a new waveform for a coil current when none exists.

        Args:
            config: The waveform configuration.
            name: Name of the waveform.
            current: Coil current value to append.
            group_name: Name of the group to place the new waveform in.
        """
        new_piecewise = (
            f"- {{type: piecewise, time: [{self.export_time}], value: [{current}]}}"
        )
        waveform = config.parser.parse_waveform(f"{name}:\n{new_piecewise}")
        config.add_waveform(waveform, [group_name])

    def _has_valid_export_time(self):
        """Check whether the export time is later than the last tendency endpoint
        in all existing coil current waveforms.

        Returns:
            True if export time is valid, False otherwise.
        """
        latest_time = None
        for i in range(len(self.coils)):
            name = f"pf_active/coil({i + 1})/current/data"
            if name in self.main_gui.config.waveform_map:
                tendencies = self.main_gui.config[name].tendencies
                if tendencies:
                    end_time = tendencies[-1].end
                    if latest_time is None or end_time > latest_time:
                        latest_time = end_time

        if latest_time is not None and latest_time >= self.export_time:
            pn.state.notifications.error(
                f"Invalid export time: {self.export_time}. It must be greater than the "
                f"last endpoint of existing coil current waveforms ({latest_time})."
            )
            return False

        return True

    def fill_pf_active(self, pf_active):
        """Update the coil currents of the provided pf_active IDS. Only coils with
        their fix checkbox checked are updated. Also stores current values as
        previous_current before the NICE run.

        Args:
            pf_active: pf_active IDS to update the coil currents for.
        """
        for i, coil in enumerate(self.coils):
            if coil.fix_current and coil.current is not None:
                pf_active.coil[i].current.data = np.array([coil.current])
            coil.previous_current = pf_active.coil[i].current.data[0]

    def sync_ui_with_pf_active(self, pf_active):
        """Synchronize UI with the current values from the pf_active IDS.

        Args:
            pf_active: pf_active IDS for which the coil currents are used.
        """
        for i, coil in enumerate(pf_active.coil):
            self.coils[i].current = coil.current.data[0]
        self._update_table()

    def update_fixed_coils_in_xml(self, xml_params: ET.Element):
        """Update XML parameters indicating which coils are fixed based on
        UI checkboxes.

        Args:
            xml_params: XML representing configuration parameters, which are updated
                in-place.
        """
        coil_groups = xml_params.find("coil_group_index").text.split()
        fixed_coils = [i for i, coil in enumerate(self.coils) if coil.fix_current]
        target_groups = {coil_groups[coil_idx] for coil_idx in fixed_coils}
        fixed_groups = sorted(list(target_groups), key=int)

        xml_params.find("n_group_fixed_index").text = str(len(fixed_groups))
        # NICE requires group_fixed_index to be filled even when there are no fixed
        # coils
        xml_params.find("group_fixed_index").text = " ".join(fixed_groups) or "-1"

    def __panel__(self):
        return self.panel
