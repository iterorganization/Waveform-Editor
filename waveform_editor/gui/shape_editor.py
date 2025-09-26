import importlib.resources
import logging
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

logger = logging.getLogger(__name__)


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
        self.nice_plotter = NicePlotter(
            communicator=self.communicator,
            plasma_shape=self.plasma_shape,
            plasma_properties=self.plasma_properties,
        )
        self.nice_settings = settings.nice

        self.xml_params_inv = ET.fromstring(
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("inverse_param.xml")
            .read_text()
        )
        self.xml_params_dir = ET.fromstring(
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("direct_param.xml")
            .read_text()
        )

        # UI Configuration
        button_start = pn.widgets.Button(name="Run", on_click=self.submit)
        button_start.disabled = (
            (
                self.plasma_shape.param.has_shape.rx.not_()
                & self.nice_settings.param.is_inverse_mode.rx()
            )
            | self.plasma_properties.param.has_properties.rx.not_()
            | self.nice_settings.param.are_required_filled.rx.not_()
        )
        button_stop = pn.widgets.Button(name="Stop", on_click=self.stop_nice)
        nice_mode_radio = pn.widgets.RadioBoxGroup.from_param(
            self.nice_settings.param.mode, inline=True, margin=(15, 20, 0, 20)
        )
        buttons = pn.Row(button_start, button_stop, nice_mode_radio)

        # Accordion does not allow dynamic titles, so use separate card for each option
        options = pn.Column(
            self._create_card(
                self.nice_settings.panel,
                "NICE Configuration",
                is_valid=self.nice_settings.param.are_required_filled.rx(),
            ),
            self._create_card(self.nice_plotter, "Plotting Parameters"),
            self._create_card(
                self.plasma_shape,
                "Plasma Shape",
                is_valid=self.plasma_shape.param.has_shape,
                visible=self.nice_settings.param.is_inverse_mode.rx(),
            ),
            self._create_card(
                pn.Column(self.plasma_properties, self.nice_plotter.profiles_pane),
                "Plasma Properties",
                is_valid=self.plasma_properties.param.has_properties,
            ),
            self._create_card(self.coil_currents, "Coil Currents"),
        )
        menu = pn.Column(
            buttons, self.communicator.terminal, sizing_mode="stretch_width"
        )
        self.panel = pn.Row(
            self.nice_plotter.flux_map_pane,
            pn.Column(
                menu,
                options,
                sizing_mode="stretch_both",
            ),
        )

    def _create_card(self, panel_object, title, is_valid=None, visible=True):
        """Create a collapsed card containing a panel object and a title.

        Args:
            panel_object: The panel object to place into the card.
            title: The title to give the card.
            is_valid: If supplied, binds the card title to update reactively using
                `_reactive_title`.
            visible: Whether the card is visible.
        """
        if is_valid:
            title = param.bind(_reactive_title, title=title, is_valid=is_valid)
        card = pn.Card(
            panel_object,
            title=title,
            sizing_mode="stretch_width",
            collapsed=True,
            visible=visible,
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

        # Only fill plasma shape for NICE inverse mode
        if self.nice_settings.is_inverse_mode:
            equilibrium.time_slice[0].boundary.outline.r = self.plasma_shape.outline_r
            equilibrium.time_slice[0].boundary.outline.z = self.plasma_shape.outline_z

        # Fill plasma properties
        equilibrium.vacuum_toroidal_field.r0 = self.plasma_properties.r0
        equilibrium.vacuum_toroidal_field.b0[0] = self.plasma_properties.b0
        slice = equilibrium.time_slice[0]
        slice.global_quantities.ip = self.plasma_properties.ip

        # These are not the p'/ff' profiles per se, the equilibrium solver will scale
        # these to maintain the total plasma current Ip
        slice.profiles_1d.dpressure_dpsi = self.plasma_properties.dpressure_dpsi
        slice.profiles_1d.f_df_dpsi = self.plasma_properties.f_df_dpsi

        # N.B. We fill psi with psi_norm. This works for NICE, but is not adhering to
        # the DD!
        slice.profiles_1d.psi = self.plasma_properties.psi_norm
        return equilibrium

    async def submit(self, event=None):
        """Submit a new equilibrium reconstruction job to NICE, passing the machine
        description IDSs and an input equilibrium IDS."""

        self.coil_currents.fill_pf_active(self.pf_active)
        if self.nice_settings.is_direct_mode:
            xml_params = self.xml_params_dir
        else:
            xml_params = self.xml_params_inv
            self.coil_currents.update_fixed_coils_in_xml(xml_params)

        # Update XML parameters:
        xml_params.find("verbose").text = str(self.nice_settings.verbose)
        equilibrium = self._create_equilibrium()
        if not self.communicator.running:
            await self.communicator.run(
                is_direct_mode=self.nice_settings.is_direct_mode
            )
        await self.communicator.submit(
            ET.tostring(xml_params, encoding="unicode"),
            equilibrium.serialize(),
            self.pf_active.serialize(),
            self.pf_passive.serialize(),
            self.wall.serialize(),
            self.iron_core.serialize(),
        )
        self.coil_currents.sync_ui_with_pf_active(self.communicator.pf_active)

    @param.depends("nice_settings.mode", watch=True)
    async def stop_nice(self, event=None):
        logger.info("Stopping NICE...")
        await self.communicator.close()

    def __panel__(self):
        return self.panel
