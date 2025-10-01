import xml.etree.ElementTree as ET

import numpy as np
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.derived_waveform import DerivedWaveform
from waveform_editor.settings import settings
from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency


class CoilCurrents(Viewer):
    coil_ui = param.List(
        doc="List of tuples containing the checkboxes and sliders for the coil currents"
    )
    export_time = param.Number(
        doc="Select a time at which coil currents will be saved to waveforms"
    )

    def __init__(self, main_gui, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice
        self.main_gui = main_gui
        self.sliders_ui = pn.Column(visible=self.param.coil_ui.rx.bool())
        guide_message = pn.pane.Markdown(
            "_To fix a coil to a specific current, enable the checkbox and provide "
            " the desired current value._",
            visible=self.param.coil_ui.rx.bool(),
            margin=(0, 10),
        )
        no_ids_message = pn.pane.Markdown(
            "Please load a valid 'pf_active' IDS in the _NICE Configuration_ settings.",
            visible=self.param.coil_ui.rx.not_(),
        )

        export_time_input = pn.widgets.FloatInput.from_param(self.param.export_time)
        confirm_button = pn.widgets.Button(
            on_click=lambda event: self._store_coil_currents(),
            name="Save Currents as Waveforms",
            margin=(30, 0, 0, 0),
        )
        self.panel = pn.Column(
            pn.Row(
                export_time_input, confirm_button, visible=self.param.coil_ui.rx.bool()
            ),
            no_ids_message,
            guide_message,
            self.sliders_ui,
        )

    @param.depends("coil_ui", watch=True)
    def _update_slider_grid(self):
        self.sliders_ui.objects = self.coil_ui

    def create_ui(self, pf_active):
        """Create the UI for each coil in the provided pf_active IDS. For each coil a
        checkbox and slider are added to fix, and set the current value, respectively.

        Args:
            pf_active: pf_active IDS containing coils with current values.
        """
        if not pf_active:
            self.coil_ui = []
            return

        new_coil_ui = []
        for coil in pf_active.coil:
            coil_current = coil.current
            checkbox = pn.widgets.Checkbox(
                margin=(30, 10, 10, 10),
                disabled=self.nice_settings.param.is_direct_mode,
            )
            slider = pn.widgets.EditableFloatSlider(
                name=f"{coil.name} Current [{coil_current.metadata.units}]",
                value=coil_current.data[0] if coil_current.data.has_value else 0.0,
                start=-5e4,
                end=5e4,
                format="0",
                width=450,
            )
            row = pn.Row(checkbox, slider)
            new_coil_ui.append(row)

        self.coil_ui = new_coil_ui

    def _store_coil_currents(self, group_name="Coil Currents"):
        """Store the current values from the coil UI sliders into the waveform
        configuration.

        Args:
            group_name: Name of the group to create new coil current waveforms in if
                they do not already exist.
        """
        coil_currents = self._get_currents()
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
        for i in range(len(self.coil_ui)):
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
        their corresponding checkbox checked are updated.

        Args:
            pf_active: pf_active IDS to update the coil currents for.
        """
        for i, coil_ui in enumerate(self.coil_ui):
            _, slider = coil_ui.objects
            pf_active.coil[i].current.data = np.array([slider.value])

    def _get_currents(self):
        """Returns the coil current values in a list."""
        coil_currents = []
        for coil_ui in self.coil_ui:
            _, slider = coil_ui.objects
            coil_currents.append(slider.value)
        return coil_currents

    def sync_ui_with_pf_active(self, pf_active):
        """Synchronize UI sliders with the current values from the pf_active IDS.

        Args:
            pf_active: pf_active IDS for which the coil currents are used.
        """
        for i, coil in enumerate(pf_active.coil):
            _, slider = self.coil_ui[i].objects
            slider.value = coil.current.data[0]

    def update_fixed_coils_in_xml(self, xml_params: ET.Element):
        """Update XML parameters indicating which coils are fixed based on
        UI checkboxes.

        Args:
            xml_params: XML representing configuration parameters, which are updated
                in-place.
        """
        coil_groups = xml_params.find("coil_group_index").text.split()
        fixed_coils = [i for i, row in enumerate(self.coil_ui) if row.objects[0].value]
        target_groups = {coil_groups[coil_idx] for coil_idx in fixed_coils}
        fixed_groups = sorted(list(target_groups), key=int)

        xml_params.find("n_group_fixed_index").text = str(len(fixed_groups))
        # NICE requires group_fixed_index to be filled even when there are no fixed
        # coils
        xml_params.find("group_fixed_index").text = " ".join(fixed_groups) or "-1"

    def __panel__(self):
        return self.panel
