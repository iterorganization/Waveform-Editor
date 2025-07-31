import asyncio
from pathlib import Path

import imas
import panel as pn
from panel.viewable import Viewer

from waveform_editor.settings import settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.nice_plotter import NicePlotter
from waveform_editor.shape_editor.plotting_params import PlottingParams
from waveform_editor.shape_editor.shape_params import ShapeParams


class ShapeEditor(Viewer):
    def __init__(self):
        self.communicator = NiceIntegration(imas.IDSFactory())
        self.plotting_params = PlottingParams()
        self.shape_params = ShapeParams()
        self._load_md_idss()
        nice_plotter = NicePlotter(
            self.communicator, self.wall, self.pf_active, self.plotting_params
        )
        self.xml_params = Path(settings.nice.xml_params).read_text()

        # UI Configuration
        buttons = pn.widgets.Button(
            name="Run",
            on_click=lambda event: asyncio.create_task(self.submit(event)),
        )
        options = pn.Accordion(
            ("NICE Configuration", pn.Param(settings.nice, show_name=False)),
            ("Plotting Parameters", pn.Param(self.plotting_params, show_name=False)),
            ("Plasma Shape", pn.Param(self.shape_params, show_name=False)),
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

    def _load_md_idss(self):
        """Loads the machine description IDSs from the NICE settings"""
        with imas.DBEntry(settings.nice.md_pf_active, "r") as entry:
            self.pf_active = entry.get_slice(
                "pf_active", 0, imas.ids_defs.CLOSEST_INTERP
            )
        with imas.DBEntry(settings.nice.md_pf_passive, "r") as entry:
            self.pf_passive = entry.get_slice(
                "pf_passive", 0, imas.ids_defs.CLOSEST_INTERP
            )
        with imas.DBEntry(settings.nice.md_wall, "r") as entry:
            self.wall = entry.get_slice("wall", 0, imas.ids_defs.CLOSEST_INTERP)
        with imas.DBEntry(settings.nice.md_iron_core, "r") as entry:
            self.iron_core = entry.get_slice(
                "iron_core", 0, imas.ids_defs.CLOSEST_INTERP
            )

    async def submit(self, event=None):
        """Submit a new equilibrium reconstruction job to NICE, passing the machine
        description IDSs and an input equilibrium IDS."""
        if self.shape_params.equilibrium_input:
            with imas.DBEntry(self.shape_params.equilibrium_input, "r") as entry:
                self.equilibrium = entry.get_slice(
                    "equilibrium",
                    self.shape_params.time_input,
                    imas.ids_defs.CLOSEST_INTERP,
                )
        else:
            # TODO:NICE requires an input equilibrium IDS with the following parameters
            # filled:
            # - time_slice[0].global_quantities.ip
            # - vacuum_toroidal_field.r0
            # - vacuum_toroidal_field.b0
            # - time_slice[0].profiles_1d.dpressure_dpsi
            # - time_slice[0].profiles_1d.f_df_dpsi
            # - time_slice[0].profiles_1d.psi
            pn.state.notifications.error(
                "Please provide a filled input equilibrium IDS"
            )
            return

        if not self.communicator.running:
            await self.communicator.run()
        await self.communicator.submit(
            self.xml_params,
            self.equilibrium.serialize(),
            self.pf_active.serialize(),
            self.pf_passive.serialize(),
            self.wall.serialize(),
            self.iron_core.serialize(),
        )

    def __panel__(self):
        return self.panel
