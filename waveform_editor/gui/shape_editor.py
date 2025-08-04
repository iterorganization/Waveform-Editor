from pathlib import Path

import imas
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.nice_plotter import NicePlotter
from waveform_editor.shape_editor.shape_params import ShapeParams


class ShapeEditor(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)

    def __init__(self):
        super().__init__()
        self.communicator = NiceIntegration(imas.IDSFactory())
        self.nice_plotter = NicePlotter(self.communicator)
        self.shape_params = ShapeParams()
        self.nice_settings = settings.nice

        # UI Configuration
        buttons = pn.widgets.Button(name="Run", on_click=self.submit)
        options = pn.Accordion(
            ("NICE Configuration", pn.Param(settings.nice, show_name=False)),
            (
                "Plotting Parameters",
                pn.Param(self.nice_plotter.plotting_params, show_name=False),
            ),
            ("Plasma Shape", pn.Param(self.shape_params, show_name=False)),
            ("Plasma Parameters", None),
            ("Coil Currents", None),
            sizing_mode="stretch_width",
        )
        menu = pn.Column(
            buttons, self.communicator.terminal, sizing_mode="stretch_width"
        )
        self.panel = pn.Row(
            pn.panel(self.nice_plotter.plot),
            pn.Column(
                menu,
                options,
                sizing_mode="stretch_both",
            ),
        )

    def _load_slice(self, uri, ids_name):
        """Load an IDS slice and return it.

        Args:
            uri: the URI to load the slice of.
            ids_name: The name of the IDS to load.
        """
        if uri:
            try:
                with imas.DBEntry(uri, "r") as entry:
                    return entry.get_slice(ids_name, 0, imas.ids_defs.CLOSEST_INTERP)
            except Exception as e:
                pn.state.notifications.error(str(e))

    @param.depends("nice_settings.md_pf_active", watch=True)
    def _load_pf_active(self):
        self.pf_active = self._load_slice(self.nice_settings.md_pf_active, "pf_active")
        self.nice_plotter.pf_active = self.pf_active
        if not self.pf_active:
            self.nice_settings.md_pf_active = ""

    @param.depends("nice_settings.md_pf_passive", watch=True)
    def _load_pf_passive(self):
        self.pf_passive = self._load_slice(
            self.nice_settings.md_pf_passive, "pf_passive"
        )
        if not self.pf_passive:
            self.nice_settings.md_pf_passive = ""

    @param.depends("nice_settings.md_wall", watch=True)
    def _load_wall(self):
        self.wall = self._load_slice(self.nice_settings.md_wall, "wall")
        self.nice_plotter.wall = self.wall
        if not self.wall:
            self.nice_settings.md_wall = ""

    @param.depends("nice_settings.md_iron_core", watch=True)
    def _load_iron_core(self):
        self.iron_core = self._load_slice(self.nice_settings.md_iron_core, "iron_core")
        if not self.iron_core:
            self.nice_settings.md_iron_core = ""

    @param.depends("nice_settings.xml_params", watch=True)
    def _load_xml_params(self):
        if self.nice_settings.xml_params:
            try:
                self.xml_params = Path(self.nice_settings.xml_params).read_text()
            except Exception:
                self.xml_params = None
                self.nice_settings.xml_params = ""

    async def submit(self, event=None):
        """Submit a new equilibrium reconstruction job to NICE, passing the machine
        description IDSs and an input equilibrium IDS."""

        input_ids_names = [
            "pf_active",
            "pf_passive",
            "wall",
            "iron_core",
        ]
        if not self.xml_params:
            pn.state.notifications.error("Please provide a path to NICE XML params")
            return

        for name in input_ids_names:
            ids = getattr(self, name)
            if not ids:
                pn.state.notifications.error(f"Please provide a valid {name} IDS")
                return

        # TODO:NICE requires an input equilibrium IDS with the following parameters
        # filled:
        # - time_slice[0].global_quantities.ip
        # - vacuum_toroidal_field.r0
        # - vacuum_toroidal_field.b0
        # - time_slice[0].profiles_1d.dpressure_dpsi
        # - time_slice[0].profiles_1d.f_df_dpsi
        # - time_slice[0].profiles_1d.psi
        try:
            with imas.DBEntry(self.shape_params.equilibrium_input, "r") as entry:
                self.equilibrium = entry.get_slice(
                    "equilibrium",
                    self.shape_params.time_input,
                    imas.ids_defs.CLOSEST_INTERP,
                )
        except Exception:
            pn.state.notifications.error("Please provide a valid equilibrium IDS")
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
