import xml.etree.ElementTree as ET
from pathlib import Path

import imas
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.nice_plotter import NicePlotter
from waveform_editor.shape_editor.plasma_properties import PlasmaProperties
from waveform_editor.shape_editor.plasma_shape import PlasmaShape
from waveform_editor.util import load_slice


class ShapeEditor(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)
    plasma_shape = param.ClassSelector(class_=PlasmaShape)
    plasma_properties = param.ClassSelector(class_=PlasmaProperties)

    def __init__(self):
        super().__init__()
        factory = imas.IDSFactory()
        self.communicator = NiceIntegration(factory)
        self.equilibrium = self.create_empty_equilibrium()
        self.plasma_shape = PlasmaShape(self.equilibrium)
        self.plasma_properties = PlasmaProperties()
        self.nice_plotter = NicePlotter(
            self.communicator, self.plasma_shape, self.equilibrium
        )
        self.has_plasma_properties = False
        self.nice_settings = settings.nice

        # UI Configuration
        button_start = pn.widgets.Button(name="Run", on_click=self.submit)
        button_start.disabled = self.plasma_shape.param.has_shape.rx.not_()
        button_stop = pn.widgets.Button(name="Stop", on_click=self.stop_nice)
        buttons = pn.Row(button_start, button_stop)
        options = pn.Accordion(
            ("NICE Configuration", pn.Param(settings.nice, show_name=False)),
            ("Plotting Parameters", pn.Param(self.nice_plotter, show_name=False)),
            ("Plasma Shape", self.plasma_shape),
            ("Plasma Parameters", self.plasma_properties),
            ("Coil Currents", None),
            sizing_mode="stretch_width",
        )
        menu = pn.Column(
            buttons, self.communicator.terminal, sizing_mode="stretch_width"
        )
        self.panel = pn.Row(
            self.nice_plotter,
            pn.Column(
                menu,
                options,
                sizing_mode="stretch_both",
            ),
        )

    @param.depends("nice_settings.md_pf_active", watch=True)
    def _load_pf_active(self):
        self.pf_active = load_slice(self.nice_settings.md_pf_active, "pf_active")
        self.nice_plotter.pf_active = self.pf_active
        if not self.pf_active:
            self.nice_settings.md_pf_active = ""

    @param.depends("nice_settings.md_pf_passive", watch=True)
    def _load_pf_passive(self):
        self.pf_passive = load_slice(self.nice_settings.md_pf_passive, "pf_passive")
        if not self.pf_passive:
            self.nice_settings.md_pf_passive = ""

    @param.depends("nice_settings.md_wall", watch=True)
    def _load_wall(self):
        self.wall = load_slice(self.nice_settings.md_wall, "wall")
        self.nice_plotter.wall = self.wall
        if not self.wall:
            self.nice_settings.md_wall = ""

    @param.depends("nice_settings.md_iron_core", watch=True)
    def _load_iron_core(self):
        self.iron_core = load_slice(self.nice_settings.md_iron_core, "iron_core")
        if not self.iron_core:
            self.nice_settings.md_iron_core = ""

    @param.depends(
        "plasma_properties.equilibrium_input",
        "plasma_properties.time_input",
        watch=True,
    )
    def _load_plasma_properties(self):
        equilibrium = load_slice(
            self.plasma_properties.equilibrium_input,
            "equilibrium",
            self.plasma_properties.time_input,
        )
        if not equilibrium:
            self.has_plasma_properties = False
            return

        self.equilibrium.time_slice[0].global_quantities.ip = equilibrium.time_slice[
            0
        ].global_quantities.ip

        self.equilibrium.vacuum_toroidal_field.r0 = equilibrium.vacuum_toroidal_field.r0
        self.equilibrium.vacuum_toroidal_field.b0[0] = (
            equilibrium.vacuum_toroidal_field.b0[0]
        )
        profiles_1d = equilibrium.time_slice[0].profiles_1d
        self.equilibrium.time_slice[
            0
        ].profiles_1d.dpressure_dpsi = profiles_1d.dpressure_dpsi
        self.equilibrium.time_slice[0].profiles_1d.f_df_dpsi = profiles_1d.f_df_dpsi
        self.equilibrium.time_slice[0].profiles_1d.psi = profiles_1d.psi
        self.has_plasma_properties = True

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

        if not self.xml_params:
            pn.state.notifications.error("Please provide a path to NICE XML params")
            return

        input_ids_names = ["pf_active", "pf_passive", "wall", "iron_core"]
        for name in input_ids_names:
            ids = getattr(self, name)
            if not ids:
                pn.state.notifications.error(f"Please provide a valid {name} IDS")
                return

        # TODO: should be done reactively
        if self.plasma_properties.input_mode == self.plasma_properties.MANUAL_INPUT:
            pn.state.notifications.error(
                "Manual plasma property input is not yet implemented"
            )
            return
        elif (
            self.plasma_properties.input_mode
            == self.plasma_properties.EQUILIBRIUM_INPUT
            and not self.has_plasma_properties
        ):
            pn.state.notifications.error(
                "Please provide a valid equilibrium IDS plasma properties"
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

    def create_empty_equilibrium(self):
        equilibrium = imas.IDSFactory().new("equilibrium")
        equilibrium.time = [0]
        equilibrium.time_slice.resize(1)
        equilibrium.vacuum_toroidal_field.b0.resize(1)
        equilibrium.ids_properties.homogeneous_time = (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )
        return equilibrium

    async def stop_nice(self, event):
        await self.communicator.close()

    def __panel__(self):
        return self.panel
