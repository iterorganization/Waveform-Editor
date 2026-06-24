import importlib.resources
import logging
import xml.etree.ElementTree as ET

import imas
import panel as pn
import param
from imas.ids_toplevel import IDSToplevel
from panel.viewable import Viewer

from waveform_editor.gui.settings import nice_mode_toggle
from waveform_editor.gui.shape_editor.coil_currents import CoilCurrents
from waveform_editor.gui.shape_editor.metrics import Metrics
from waveform_editor.gui.shape_editor.nice_plotter import NicePlotter
from waveform_editor.gui.shape_editor.plasma_properties import PlasmaProperties
from waveform_editor.gui.shape_editor.plasma_shape import PlasmaShape
from waveform_editor.gui.shape_editor.settings_modal import SettingsModal
from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration

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
    use_previous_run = param.Boolean(
        default=False, doc="Use previous run as warm start"
    )

    def __init__(self, main_gui):
        super().__init__()
        self.factory = imas.IDSFactory()
        self.terminal = pn.widgets.Terminal(
            sizing_mode="stretch_width",
            options={"scrollback": 10000, "wrap": True},
            height=200,
            max_width=750,
        )
        self.communicator = NiceIntegration(
            self.factory,
            on_output=self.terminal.write,
            on_run_finished=self._on_nice_run_finished,
        )
        self.plasma_shape = PlasmaShape()
        self.plasma_properties = PlasmaProperties()
        self.coil_currents = CoilCurrents(main_gui)
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
        disabled_expr = (
            (
                self.plasma_shape.param.has_shape.rx.not_()
                & self.nice_settings.param.is_inverse_mode.rx()
            )
            | self.plasma_properties.param.has_properties.rx.not_()
            | self.nice_settings.param.are_required_filled.rx.not_()
        )

        button_start = pn.widgets.Button(
            name="Run",
            button_type="primary",
            icon="player-play",
            on_click=self.submit,
            description=pn.bind(
                lambda disabled: (
                    "Cannot run: missing required inputs"
                    if disabled
                    else "Run simulation"
                ),
                disabled_expr,
            ),
            disabled=disabled_expr,
            margin=(10, 0, 2, 0),
        )
        button_stop = pn.widgets.Button(
            name="Stop",
            button_type="danger",
            icon="player-stop",
            on_click=self.stop_nice,
            margin=(10, 10, 2, 0),
        )
        nice_mode_radio = nice_mode_toggle(self.nice_settings, margin=(10, 0, 2, 0))
        warm_start_switch = pn.widgets.Switch.from_param(
            self.param.use_previous_run,
            name="",
            disabled=self.communicator.param.can_warm_start.rx.not_(),
            margin=(20, 15, 2, 10),
        )
        tooltip_msg = (
            "Enable warm start to use the previous run's equilibrium as the "
            "initial guess for the next run. This can improve convergence."
        )
        warm_start_tooltip = pn.widgets.TooltipIcon(
            value=pn.bind(
                lambda can: (
                    tooltip_msg
                    if can
                    else f"{tooltip_msg}\n\nNo previous run is available yet. "
                    "Run NICE once to allow warm starting. "
                ),
                self.communicator.param.can_warm_start,
            ),
            margin=(5, 0, 2, 0),
        )
        settings_modal = SettingsModal(self.nice_plotter)
        buttons = pn.Row(
            nice_mode_radio,
            pn.widgets.StaticText(value="Warm start", margin=(15, 0, 2, 10)),
            warm_start_switch,
            warm_start_tooltip,
            pn.Spacer(sizing_mode="stretch_width"),
            button_stop,
            button_start,
            align="center",
        )

        self.metrics = Metrics()
        # Accordion does not allow dynamic titles, so use separate card for each option
        inputs = pn.Column(
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
            self._create_card(
                self.coil_currents,
                "Coil Currents",
                visible=self.nice_settings.md_pf_active.param.loaded.rx(),
            ),
        )
        menu = pn.Column(buttons, self.terminal, sizing_mode="stretch_width")
        header = pn.Row(
            pn.HSpacer(),
            settings_modal,
            sizing_mode="stretch_width",
        )

        left_col = pn.Column(
            header,
            self.nice_plotter.flux_map_pane,
            self.metrics,
            width=self.nice_plotter.flux_map_pane.width,
        )

        self.panel = pn.Row(
            left_col,
            pn.Column(
                menu,
                pn.layout.Divider(),
                inputs,
                sizing_mode="stretch_both",
            ),
        )

    def _create_card(
        self, panel_object, title, is_valid=None, visible=True, collapsed=True
    ):
        """Create a collapsed card containing a panel object and a title.

        Args:
            panel_object: The panel object to place into the card.
            title: The title to give the card.
            is_valid: If supplied, binds the card title to update reactively using
                `_reactive_title`.
            visible: Whether the card is visible.
            collapsed: Whether the card is collapsed.
        """
        if is_valid:
            title = param.bind(_reactive_title, title=title, is_valid=is_valid)
        return pn.Card(
            panel_object,
            title=title,
            sizing_mode="stretch_width",
            collapsed=collapsed,
            visible=visible,
        )

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

    @param.depends(
        "nice_settings.md_pf_active.uri",
        "nice_settings.md_pf_passive.uri",
        "nice_settings.md_wall.uri",
        "nice_settings.md_iron_core.uri",
        watch=True,
    )
    def _disable_warm_start(self):
        self.use_previous_run = False
        self.communicator.can_warm_start = False

    @param.depends("nice_settings.md_pf_active.uri", watch=True)
    def _load_pf_active(self):
        self.pf_active = self._load_slice(
            self.nice_settings.md_pf_active.uri, "pf_active"
        )
        self.nice_plotter.pf_active = self.pf_active
        self.coil_currents.create_ui(self.pf_active)
        self.nice_settings.md_pf_active.loaded = self.pf_active is not None

    @param.depends("nice_settings.md_pf_passive.uri", watch=True)
    def _load_pf_passive(self):
        self.pf_passive = self._load_slice(
            self.nice_settings.md_pf_passive.uri, "pf_passive"
        )
        self.nice_settings.md_pf_passive.loaded = self.pf_passive is not None

    @param.depends("nice_settings.md_wall.uri", watch=True)
    def _load_wall(self):
        self.wall = self._load_slice(self.nice_settings.md_wall.uri, "wall")
        self.nice_plotter.wall = self.wall
        self.nice_settings.md_wall.loaded = self.wall is not None

    @param.depends("nice_settings.md_iron_core.uri", watch=True)
    def _load_iron_core(self):
        self.iron_core = self._load_slice(
            self.nice_settings.md_iron_core.uri, "iron_core"
        )
        self.nice_settings.md_iron_core.loaded = self.iron_core is not None

    def _create_equilibrium(self):
        """Create and initialize an equilibrium IDS.

        Returns:
            The equilibrium IDS
        """
        equilibrium = self.factory.new("equilibrium")
        equilibrium.ids_properties.homogeneous_time = (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )
        equilibrium.time = [0.0]
        equilibrium.time_slice.resize(1)
        equilibrium.vacuum_toroidal_field.b0.resize(1)

        return equilibrium

    def _fill_equilibrium(self, equilibrium):
        """Fill equilibrium IDS with plasma boundary and core profiles.

        Args:
            equilibrium: equilibrium IDS object to fill
        """
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

    def _on_nice_run_finished(self, success):
        if success:
            pn.state.notifications.success("NICE run complete.")
        else:
            pn.state.notifications.error(
                "NICE did not converge. Check the terminal for details."
            )

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

        use_previous_equilibrium = (
            self.use_previous_run and self.communicator.can_warm_start
        )
        if use_previous_equilibrium:
            pn.state.notifications.info("Starting from previous equilibrium.")
            equilibrium = self.communicator.equilibrium
        else:
            equilibrium = self._create_equilibrium()
        self._fill_equilibrium(equilibrium)

        if self.nice_settings.is_direct_mode:
            start_from_scratch = "0" if use_previous_equilibrium else "1"
            xml_params.find("algoStartFromScratch").text = start_from_scratch
            xml_params.find("algoStartFromScratchReconAB").text = start_from_scratch
            xml_params.find("algoStartPsiFromInData").text = (
                "1" if use_previous_equilibrium else "0"
            )

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
        self._update_metrics()

    def _update_metrics(self):
        eq = self.communicator.equilibrium
        global_quantities = eq.time_slice[0].global_quantities
        boundary = eq.time_slice[0].boundary

        self.metrics.metrics = {
            self.metrics.ELONGATION: float(boundary.elongation),
            self.metrics.TRIANGULARITY: float(boundary.triangularity),
            self.metrics.TRI_UPPER: float(boundary.triangularity_upper),
            self.metrics.TRI_LOWER: float(boundary.triangularity_lower),
            self.metrics.MAJOR_RADIUS: float(boundary.geometric_axis.r),
            self.metrics.VERTICAL: float(boundary.geometric_axis.z),
            self.metrics.MINOR_RADIUS: float(boundary.minor_radius),
            self.metrics.Q95: float(global_quantities.q_95),
        }

    @param.depends("nice_settings.mode", watch=True)
    async def stop_nice(self, event=None):
        logger.info("Stopping NICE...")
        await self.communicator.close()

    def __panel__(self):
        return self.panel
