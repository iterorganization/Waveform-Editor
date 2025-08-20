import importlib.resources
import xml.etree.ElementTree as ET

import imas
import panel as pn
import param
from imas.ids_toplevel import IDSToplevel
from panel.viewable import Viewer

from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.coil_currents import CoilCurrents
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.nice_plotter import NicePlotter
from waveform_editor.shape_editor.plasma_properties import PlasmaProperties
from waveform_editor.shape_editor.plasma_shape import PlasmaShape


def _reactive_title(title, is_valid):
    return title if is_valid else f"{title} ⚠️"


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
        self.factory = imas.IDSFactory()
        self.communicator = NiceIntegration(self.factory)
        self.plasma_shape = PlasmaShape()
        self.plasma_properties = PlasmaProperties()
        self.coil_currents = CoilCurrents()
        self.nice_plotter = NicePlotter(self.communicator, self.plasma_shape)
        self.nice_settings = settings.nice

        self.xml_params = ET.fromstring(
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("param.xml")
            .read_text()
        )

        # UI Configuration
        button_start = pn.widgets.Button(name="Run", on_click=self.submit)
        button_start.disabled = (
            self.plasma_shape.param.has_shape.rx.not_()
            | self.plasma_properties.param.has_properties.rx.not_()
            | param.rx(self.nice_settings.required_params_filled).rx.not_()
        )
        button_stop = pn.widgets.Button(name="Stop", on_click=self.stop_nice)
        buttons = pn.Row(button_start, button_stop)

        # Accordion does not allow dynamic titles, so use separate card for each option
        options = pn.Column(
            self._create_card(
                self.nice_settings.panel,
                "NICE Configuration",
                is_valid=param.rx(self.nice_settings.required_params_filled),
            ),
            self._create_card(
                pn.Param(self.nice_plotter, show_name=False), "Plotting Parameters"
            ),
            self._create_card(
                self.plasma_shape,
                "Plasma Shape",
                is_valid=self.plasma_shape.param.has_shape,
            ),
            self._create_card(
                self.plasma_properties,
                "Plasma Properties",
                is_valid=self.plasma_properties.param.has_properties,
            ),
            self._create_card(self.coil_currents, "Coil Currents"),
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

    def _create_card(self, panel_object, title, is_valid=None):
        """Create a collapsed card containing a panel object and a title.

        Args:
            panel_object: The panel object to place into the card.
            title: The title to give the card.
            is_valid: If supplied, binds the card title to update reactively using
                `_reactive_title`.
        """
        if is_valid:
            title = param.bind(_reactive_title, title=title, is_valid=is_valid)
        card = pn.Card(
            panel_object,
            title=title,
            sizing_mode="stretch_width",
            collapsed=True,
        )
        return card

    def _load_slice(self, uri, ids_name, time=0):
        """Load an IDS slice and return it.

        Args:
            uri: the URI to load the slice of.
            ids_name: The name of the IDS to load.
            time: the time step to load slice of.
        """
        if uri:
            try:
                with imas.DBEntry(uri, "r") as entry:
                    return entry.get_slice(ids_name, time, imas.ids_defs.CLOSEST_INTERP)
            except Exception as e:
                pn.state.notifications.error(str(e))

    @param.depends("nice_settings.md_pf_active", watch=True)
    def _load_pf_active(self):
        self.pf_active = self._load_slice(self.nice_settings.md_pf_active, "pf_active")
        self.nice_plotter.pf_active = self.pf_active
        self.coil_currents.create_ui(self.pf_active)
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

    def _create_equilibrium(self):
        """Create an empty equilibrium IDS and fill the plasma shape parameters and
        plasma properties.

        Returns:
            The filled equilibrium IDS
        """
        equilibrium = self.factory.new("equilibrium")
        equilibrium.ids_properties.homogeneous_time = (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )
        equilibrium.time = [0.0]
        equilibrium.time_slice.resize(1)
        equilibrium.vacuum_toroidal_field.b0.resize(1)

        # Fill plasma shape
        equilibrium.time_slice[0].boundary.outline.r = self.plasma_shape.outline_r
        equilibrium.time_slice[0].boundary.outline.z = self.plasma_shape.outline_z

        # Fill plasma properties
        equilibrium.vacuum_toroidal_field.r0 = self.plasma_properties.r0
        equilibrium.vacuum_toroidal_field.b0[0] = self.plasma_properties.b0
        slice = equilibrium.time_slice[0]
        slice.global_quantities.ip = self.plasma_properties.ip
        slice.profiles_1d.dpressure_dpsi = self.plasma_properties.dpressure_dpsi
        slice.profiles_1d.f_df_dpsi = self.plasma_properties.f_df_dpsi
        slice.profiles_1d.psi = self.plasma_properties.psi
        return equilibrium

    async def submit(self, event=None):
        """Submit a new equilibrium reconstruction job to NICE, passing the machine
        description IDSs and an input equilibrium IDS."""

        self.coil_currents.fill_pf_active(self.pf_active)
        # Update XML parameters:
        self.coil_currents.update_fixed_coils_in_xml(self.xml_params)
        self.xml_params.find("verbose").text = str(self.nice_settings.verbose)
        equilibrium = self._create_equilibrium()
        if not self.communicator.running:
            await self.communicator.run()
        await self.communicator.submit(
            ET.tostring(self.xml_params, encoding="unicode"),
            equilibrium.serialize(),
            self.pf_active.serialize(),
            self.pf_passive.serialize(),
            self.wall.serialize(),
            self.iron_core.serialize(),
        )
        self.coil_currents.sync_ui_with_pf_active(self.communicator.pf_active)

    async def stop_nice(self, event):
        await self.communicator.close()

    def __panel__(self):
        return self.panel
