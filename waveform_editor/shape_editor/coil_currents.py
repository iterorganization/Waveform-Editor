import xml.etree.ElementTree as ET

import numpy as np
import panel as pn
import param
from bokeh.models.formatters import PrintfTickFormatter
from panel.viewable import Viewer


class CoilCurrents(Viewer):
    coil_ui = param.List()

    def __init__(self):
        super().__init__()
        self.slider_grid = pn.GridBox(ncols=2, visible=self.param.coil_ui.rx.bool())
        self.empty_message = pn.pane.Markdown(
            "Please load a valid 'pf_active' IDS",
            visible=self.param.coil_ui.rx.not_(),
        )
        self.panel = pn.Column(self.empty_message, self.slider_grid)

    def create_ui(self, pf_active):
        if not pf_active:
            self.coil_ui = []
        else:
            new_coil_ui = []
            for coil in pf_active.coil:
                coil_current = coil.current
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
                checkbox = pn.widgets.Checkbox(margin=(30, 10, 10, 10))

                def toggle_slider(event, s=slider):
                    s.disabled = not event.new

                checkbox.param.watch(toggle_slider, "value")
                row = pn.Row(checkbox, slider)
                new_coil_ui.append(row)

            self.coil_ui = new_coil_ui

        self.slider_grid.objects = self.coil_ui

    def fill_coil_currents(self, pf_active):
        for i, coil_ui in enumerate(self.coil_ui):
            checkbox, slider = coil_ui.objects
            if checkbox.value:
                pf_active.coil[i].current.data = np.array([slider.value])

    def set_coil_current_ui(self, pf_active):
        for i, coil in enumerate(pf_active.coil):
            _, slider = self.coil_ui[i].objects
            slider.value = coil.current.data[0]

    def set_fixed_coils(self, xml_string):
        n_group_fixed_index = sum(
            cb.value for cb, _ in (row.objects for row in self.coil_ui)
        )
        if n_group_fixed_index == 0:
            group_fixed_index = -1
        else:
            group_fixed_index = " ".join(
                str(i) for i, row in enumerate(self.coil_ui) if row.objects[0].value
            )
        params = {
            "n_group_fixed_index": n_group_fixed_index,
            "group_fixed_index": str(group_fixed_index),
        }
        print(params)
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
