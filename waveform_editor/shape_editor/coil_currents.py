import xml.etree.ElementTree as ET

import numpy as np
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.settings import NiceSettings


class CoilCurrents(Viewer):
    coil_ui = param.List(
        doc="List of tuples containing the checkboxes and sliders for the coil currents"
    )
    nice_mode = param.Selector(allow_refs=True)

    def __init__(self, **params):
        super().__init__(**params)
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
        self.panel = pn.Column(no_ids_message, guide_message, self.sliders_ui)

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
                disabled=self.param.nice_mode.rx() == NiceSettings.DIRECT_MODE,
            )
            slider = pn.widgets.EditableFloatSlider(
                name=f"{coil.name} Current [{coil_current.metadata.units}]",
                value=coil_current.data[0] if coil_current.data.has_value else 0.0,
                start=-5e4,
                end=5e4,
                disabled=checkbox.param.value.rx.not_()
                & (self.param.nice_mode.rx() == NiceSettings.INVERSE_MODE),
                format="0",
                width=450,
            )
            row = pn.Row(checkbox, slider)
            new_coil_ui.append(row)

        self.coil_ui = new_coil_ui

    def fill_pf_active(self, pf_active):
        """Update the coil currents of the provided pf_active IDS. Only coils with
        their corresponding checkbox checked are updated.

        Args:
            pf_active: pf_active IDS to update the coil currents for.
        """
        for i, coil_ui in enumerate(self.coil_ui):
            checkbox, slider = coil_ui.objects
            if checkbox.value or self.nice_mode == NiceSettings.DIRECT_MODE:
                pf_active.coil[i].current.data = np.array([slider.value])

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
