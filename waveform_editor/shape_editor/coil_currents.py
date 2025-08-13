import xml.etree.ElementTree as ET

import numpy as np
import panel as pn
from bokeh.models.formatters import PrintfTickFormatter
from panel.viewable import Viewer


class CoilCurrents(Viewer):
    def __init__(self):
        super().__init__()
        self.coil_currents = []
        self.panel = pn.Column()

    def update_coils(self, pf_active):
        if not pf_active or not hasattr(pf_active, "coil"):
            self.panel.objects = [
                pn.pane.Markdown("Please load a valid 'pf_active' IDS")
            ]
            self.coil_currents.clear()
            return

        for coil in pf_active.coil:
            coil_current = coil.current
            slider = pn.widgets.FloatSlider(
                name=str(coil.name),
                value=coil_current.data[0],
                start=-5e4,
                end=5e4,
                disabled=True,
                format=PrintfTickFormatter(
                    format=f"%.3f [{coil_current.metadata.units}]"
                ),
            )
            checkbox = pn.widgets.Checkbox()

            def toggle_slider(event, s=slider):
                s.disabled = not event.new

            checkbox.param.watch(toggle_slider, "value")
            row = pn.Row(checkbox, slider)
            self.coil_currents.append(row)

        self.panel.objects = self.coil_currents

    def set_coil_currents(self, pf_active):
        for i, coil_ui in enumerate(self.coil_currents):
            checkbox, slider = coil_ui.objects
            if checkbox.value:
                pf_active.coil[i].current.data = np.array([slider.value])

    def set_fixed_coils(self, xml_string):
        n_group_fixed_index = sum(
            cb.value for cb, _ in (row.objects for row in self.coil_currents)
        )
        if n_group_fixed_index == 0:
            group_fixed_index = -1
        else:
            group_fixed_index = " ".join(
                str(i)
                for i, row in enumerate(self.coil_currents)
                if row.objects[0].value
            )
        params = {
            "n_group_fixed_index": n_group_fixed_index,
            "group_fixed_index": str(group_fixed_index),
        }
        return self._update_xml_params(xml_string, params)

    def _update_xml_params(self, xml_string, params):
        root = ET.fromstring(xml_string)
        for key, val in params.items():
            elem = root.find(key)
            if elem is not None:
                elem.text = str(val)
        return ET.tostring(root, encoding="unicode")

    def __panel__(self):
        return self.panel
