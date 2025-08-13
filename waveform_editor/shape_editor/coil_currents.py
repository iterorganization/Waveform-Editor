import xml.etree.ElementTree as ET

import numpy as np
import panel as pn
import param
from bokeh.models.formatters import PrintfTickFormatter
from panel.viewable import Viewer


class CoilCurrents(Viewer):
    coil_ui = param.List(
        doc="List of tuples containing the checkboxes and sliders for the coil currents"
    )

    def __init__(self):
        super().__init__()
        self.grid_box = pn.GridBox(ncols=2, visible=self.param.coil_ui.rx.bool())
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
        self.panel = pn.Column(no_ids_message, guide_message, self.grid_box)

    @param.depends("coil_ui", watch=True)
    def _update_slider_grid(self):
        self.grid_box.objects = self.coil_ui

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
            checkbox = pn.widgets.Checkbox(value=False, margin=(30, 10, 10, 10))
            slider = pn.widgets.EditableFloatSlider(
                name=f"{coil.name}",
                value=coil_current.data[0],
                start=-5e4,
                end=5e4,
                disabled=True,
                format=PrintfTickFormatter(
                    format=f"%.0f {coil_current.metadata.units}"
                ),
                width=450,
            )

            def toggle_slider(event, slider=slider):
                slider.disabled = not event.new

            checkbox.param.watch(toggle_slider, "value")
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
            if checkbox.value:
                pf_active.coil[i].current.data = np.array([slider.value])

    def sync_ui_with_pf_active(self, pf_active):
        """Synchronize UI sliders with the current values from the pf_active IDS.

        Args:
            pf_active: pf_active IDS for which the coil currents are used.
        """
        for i, coil in enumerate(pf_active.coil):
            _, slider = self.coil_ui[i].objects
            slider.value = coil.current.data[0]

    def update_fixed_coils_in_xml(self, xml_string):
        """Generate XML parameters indicating which coils are fixed based on
        UI checkboxes.

        Args:
            xml_string: XML string representing configuration parameters.

        Returns:
            Updated XML string with the `n_group_fixed_index` and `group_fixed_index`
                elements modified.
        """
        n_group_fixed_index = sum(
            cb.value for cb, _ in (row.objects for row in self.coil_ui)
        )
        if n_group_fixed_index == 0:
            # NICE requires group_fixed_index to be filled even when there are no fixed
            # coils, so set to invalid index
            group_fixed_index = str(-1)
        else:
            group_fixed_index = " ".join(
                str(i) for i, row in enumerate(self.coil_ui) if row.objects[0].value
            )
        params = {
            "n_group_fixed_index": n_group_fixed_index,
            "group_fixed_index": group_fixed_index,
        }
        return self._update_xml_params(xml_string, params)

    def _update_xml_params(self, xml_string, params):
        """Update XML elements with specified parameter values.

        Args:
            xml_string: Original XML configuration as a string.
            params: Dictionary mapping XML element names to new values.

        Returns:
            Updated XML as a string.
        """
        root = ET.fromstring(xml_string)
        for key, val in params.items():
            elem = root.find(key)
            if elem is not None:
                elem.text = str(val)
        return ET.tostring(root, encoding="unicode")

    def __panel__(self):
        return self.panel
