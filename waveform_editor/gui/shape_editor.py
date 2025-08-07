import importlib.resources

import imas
import panel as pn
import param
from imas.ids_toplevel import IDSToplevel
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

    pf_active = param.ClassSelector(class_=IDSToplevel)
    pf_passive = param.ClassSelector(class_=IDSToplevel)
    wall = param.ClassSelector(class_=IDSToplevel)
    iron_core = param.ClassSelector(class_=IDSToplevel)

    def __init__(self):
        super().__init__()
        factory = imas.IDSFactory()
        self.communicator = NiceIntegration(factory)
        self.equilibrium = self.create_empty_equilibrium()
        self.plasma_shape = PlasmaShape(self.equilibrium)
        self.plasma_properties = PlasmaProperties(self.equilibrium)
        self.nice_plotter = NicePlotter(
            self.communicator, self.plasma_shape, self.equilibrium
        )
        self.nice_settings = settings.nice

        with (
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("param.xml")
            .open("r") as f
        ):
            self.xml_params = f.read()

        # UI Configuration
        button_start = pn.widgets.Button(name="Run", on_click=self.submit)
        button_start.disabled = (
            self.plasma_shape.param.has_shape.rx.not_()
            | self.plasma_properties.param.has_properties.rx.not_()
            | self.param.pf_active.rx.not_()
            | self.param.pf_passive.rx.not_()
            | self.param.iron_core.rx.not_()
            | self.param.wall.rx.not_()
        )
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

    def create_empty_equilibrium(self):
        equilibrium = imas.IDSFactory().new("equilibrium")
        equilibrium.time = [0]
        equilibrium.time_slice.resize(1)
        equilibrium.vacuum_toroidal_field.b0.resize(1)
        equilibrium.ids_properties.homogeneous_time = (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )
        return equilibrium

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

    async def submit(self, event=None):
        """Submit a new equilibrium reconstruction job to NICE, passing the machine
        description IDSs and an input equilibrium IDS."""

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

    async def stop_nice(self, event):
        await self.communicator.close()

    def __panel__(self):
        return self.panel
