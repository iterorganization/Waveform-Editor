import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path

import imas
import panel as pn
from panel.viewable import Viewer
from panel.widgets import FloatInput

from waveform_editor.settings import settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.nice_params import NiceParams
from waveform_editor.shape_editor.nice_plotter import NicePlotter


class ShapeEditor(Viewer):
    def __init__(self):
        self.xml_params = Path(settings.nice.xml_params).read_text()
        self.communicator = NiceIntegration(imas.IDSFactory())
        nice_params = NiceParams()
        self.nice_plotter = NicePlotter(self.communicator)
        reset_button = pn.widgets.ButtonIcon(
            icon="restore", size="25px", name="Restore Defaults"
        )
        reset_button.on_click(lambda event: nice_params.reset())
        self.shape_editor = pn.Column(
            pn.Row(
                pn.Param(self.communicator.param),
                pn.Column(
                    pn.widgets.Button(
                        name="Run",
                        on_click=lambda event: asyncio.create_task(
                            self.submit(nice_params, event)
                        ),
                    ),
                    pn.widgets.Button(name="Start NICE", on_click=self.start_nice),
                    pn.widgets.Button(name="Stop NICE", on_click=self.stop_nice),
                ),
            ),
            pn.Tabs(
                ("NICE output", self.communicator.terminal),
                (
                    "NICE plot",
                    pn.Row(
                        pn.Column(
                            reset_button,
                            pn.Param(self.nice_plotter.param.levels),
                            pn.Param(
                                nice_params,
                                widgets={
                                    "epsStopInv": {"widget_type": pn.widgets.FloatInput}
                                },
                            ),
                        ),
                        pn.panel(self.nice_plotter.plot),
                    ),
                ),
                ("NICE settings", settings.panel),
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
        with imas.DBEntry(
            "imas:hdf5?path=/home/sebbe/projects/iter_python/Waveform-Editor/data/nice-input-dd4",
            "r",
        ) as entry:
            time = plot_params.time
            eq = entry.get_slice("equilibrium", time, imas.ids_defs.CLOSEST_INTERP)
            pfa = entry.get_slice("pf_active", time, imas.ids_defs.CLOSEST_INTERP)
            pfp = entry.get_slice("pf_passive", time, imas.ids_defs.CLOSEST_INTERP)
            wall = entry.get_slice("wall", time, imas.ids_defs.CLOSEST_INTERP)
            iron_core = entry.get_slice("iron_core", time, imas.ids_defs.CLOSEST_INTERP)
        self.nice_plotter.wall = wall
        updated_xml = self._update_xml_params(self.xml_params, plot_params)
        if not self.communicator.running:
            await self.communicator.run()
        await self.communicator.submit(
            updated_xml,
            eq.serialize(),
            pfa.serialize(),
            pfp.serialize(),
            wall.serialize(),
            iron_core.serialize(),
        )

    async def start_nice(self, event):
        await self.communicator.run()

    async def stop_nice(self, event):
        await self.communicator.close()

    def __panel__(self):
        return self.shape_editor
