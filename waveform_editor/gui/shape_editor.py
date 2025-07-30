import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path

import imas
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.settings import settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.nice_plotter import NicePlotter
from waveform_editor.shape_editor.plotting_params import PlottingParams


# placeholder params class
class NiceParams(param.Parameterized):
    pass


class ShapeEditor(Viewer):
    def __init__(self):
        time = 249.5
        with imas.DBEntry(settings.nice.md_pf_active, "r") as entry:
            self.pfa = entry.get_slice("pf_active", time, imas.ids_defs.CLOSEST_INTERP)
        with imas.DBEntry(settings.nice.md_pf_active, "r") as entry:
            self.pfp = entry.get_slice("pf_passive", time, imas.ids_defs.CLOSEST_INTERP)
        with imas.DBEntry(settings.nice.md_wall, "r") as entry:
            self.wall = entry.get_slice("wall", time, imas.ids_defs.CLOSEST_INTERP)
        with imas.DBEntry(settings.nice.md_iron_core, "r") as entry:
            self.iron_core = entry.get_slice(
                "iron_core", time, imas.ids_defs.CLOSEST_INTERP
            )
        with imas.DBEntry(settings.nice.equilibrium_input, "r") as entry:
            self.eq = entry.get_slice("equilibrium", time, imas.ids_defs.CLOSEST_INTERP)

        self.xml_params = Path(settings.nice.xml_params).read_text()
        self.communicator = NiceIntegration(imas.IDSFactory())

        nice_params = NiceParams()
        plotting_params = PlottingParams()
        nice_plotter = NicePlotter(
            self.communicator, self.wall, self.pfa, plotting_params
        )

        buttons = pn.widgets.Button(
            name="Run",
            on_click=lambda event: asyncio.create_task(self.submit(nice_params, event)),
        )

        # Options placeholders
        options = pn.Accordion(
            ("Plotting Parameters", pn.Param(plotting_params, show_name=False)),
            ("NICE Configuration", pn.Param(settings.nice, show_name=False)),
            ("Plasma Shape", None),
            ("Plasma Parameters", None),
            ("Coil Currents", None),
            sizing_mode="stretch_width",
            toggle=True,
        )

        menu = pn.Column(
            buttons, self.communicator.terminal, sizing_mode="stretch_width"
        )

        self.panel = pn.Row(
            pn.panel(nice_plotter.plot),
            pn.Column(
                menu,
                options,
                sizing_mode="stretch_both",
            ),
        )

    def _update_xml_params(self, xml_string, params):
        root = ET.fromstring(xml_string)
        for key in params.param:
            elem = root.find(key)
            if elem is not None:
                val = getattr(params, key)
                if isinstance(val, bool):
                    val = int(val)
                print(f"Changed {key} from {elem.text} to {str(val)}")
                elem.text = str(val)
        return ET.tostring(root, encoding="unicode")

    async def submit(self, plot_params, event=None):
        updated_xml = self._update_xml_params(self.xml_params, plot_params)
        if not self.communicator.running:
            await self.communicator.run()
        await self.communicator.submit(
            updated_xml,
            self.eq.serialize(),
            self.pfa.serialize(),
            self.pfp.serialize(),
            self.wall.serialize(),
            self.iron_core.serialize(),
        )

    async def stop_nice(self, event):
        await self.communicator.close()

    def __panel__(self):
        return self.panel
