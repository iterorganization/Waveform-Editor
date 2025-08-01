import asyncio
from pathlib import Path

import imas
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.nice_plotter import NicePlotter
from waveform_editor.shape_editor.plotting_params import PlottingParams
from waveform_editor.shape_editor.shape_params import ShapeParams


class ShapeEditor(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)

    def __init__(self):
        self.communicator = NiceIntegration(imas.IDSFactory())
        self.plotting_params = PlottingParams()
        self.nice_plotter = NicePlotter(self.communicator, self.plotting_params)
        super().__init__()
        self.shape_params = ShapeParams()
        self.nice_settings = settings.nice
        self.xml_params = None

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
            pn.panel(self.nice_plotter.plot),
            pn.Column(
                menu,
                options,
                sizing_mode="stretch_both",
            ),
        )

    def _load_slice(self, nice_settings_uri, ids_name, set_plot_ids=False):
        """Load an IDS slice from the IMAS database and assign it to attributes.

        Args:
            nice_settings_uri: Name of the IDS attribute of settings.nice that
                holds the URI.
            ids_name: Name of the IDS slice to load.
            set_plot_ids: If True, also assign the loaded IDS slice to
                `self.nice_plotter.{ids_name}`.
        """
        setattr(self, ids_name, None)
        md_value = getattr(self.nice_settings, nice_settings_uri)
        if md_value:
            try:
                with imas.DBEntry(md_value, "r") as entry:
                    data = entry.get_slice(ids_name, 0, imas.ids_defs.CLOSEST_INTERP)
                    setattr(self, ids_name, data)
                    if set_plot_ids:
                        setattr(self.nice_plotter, ids_name, data)
            except Exception as e:
                pn.state.notifications.error(str(e))
                setattr(self.nice_settings, nice_settings_uri, "")

    @param.depends("nice_settings.md_pf_active", watch=True)
    def _load_pf_active(self):
        self._load_slice("md_pf_active", "pf_active", set_plot_ids=True)

    @param.depends("nice_settings.md_pf_passive", watch=True)
    def _load_pf_passive(self):
        self._load_slice("md_pf_passive", "pf_passive")

    @param.depends("nice_settings.md_wall", watch=True)
    def _load_wall(self):
        self._load_slice("md_wall", "wall", set_plot_ids=True)

    @param.depends("nice_settings.md_iron_core", watch=True)
    def _load_iron_core(self):
        self._load_slice("md_iron_core", "iron_core")

    @param.depends("nice_settings.xml_params", watch=True)
    def _load_xml_params(self):
        if self.nice_settings.xml_params:
            self.xml_params = Path(settings.nice.xml_params).read_text()

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
