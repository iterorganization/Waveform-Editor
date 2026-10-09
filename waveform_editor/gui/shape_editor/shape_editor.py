import copy
import importlib.resources
import logging
import xml.etree.ElementTree as ET
from datetime import datetime

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
from waveform_editor.gui.shape_editor.waveform_sync import WaveformSync
from waveform_editor.gui.util import DragHandle, set_xml_parameter
from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.gaps import MACHINE_GAPS
from waveform_editor.shape_editor.nice_integration import NiceIntegration

logger = logging.getLogger(__name__)

# NICE reads the desired boundary into an array of this fixed size
# (MAX_PLASMA_BOUNDARY_POINTS in its solver_structs.h)
MAX_BOUNDARY_POINTS = 5000


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
            min_height=200,
            stylesheets=[":host { min-width: 0; overflow: hidden; }"],
        )
        self.communicator = NiceIntegration(
            self.factory,
            on_output=self.terminal.write,
            on_run_finished=self._on_nice_run_finished,
        )
        self.plasma_shape = PlasmaShape()
        self.plasma_properties = PlasmaProperties()
        self.coil_currents = CoilCurrents()
        self.nice_plotter = NicePlotter(
            communicator=self.communicator,
            plasma_shape=self.plasma_shape,
            plasma_properties=self.plasma_properties,
        )
        # Converged runs as (label, equilibrium, pf_active) tuples, oldest first
        self.run_history = []
        self.run_select = pn.widgets.Select(
            options={},
            disabled=True,
            width=260,
            margin=(10, 0, 2, 10),
        )
        self.run_select.param.watch(self._restore_run, "value")
        self.nice_settings = settings.nice

        self.xml_text = (
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("param.xml")
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
            styles={"margin-left": "auto"},
        )
        nice_mode_radio = nice_mode_toggle(self.nice_settings, margin=(10, 0, 2, 0))
        warm_start_switch = pn.widgets.Switch.from_param(
            self.param.use_previous_run,
            name="",
            disabled=self.communicator.param.converged.rx.not_(),
            margin=(20, 15, 2, 10),
        )
        tooltip_msg = (
            "Enable warm start to use the previous run's equilibrium as the "
            "initial guess for the next run. This can improve convergence."
        )
        warm_start_label = pn.pane.HTML(
            pn.bind(
                lambda can: (
                    f'<span title="{tooltip_msg}">Warm start</span>'
                    if can
                    else f'<span title="{tooltip_msg} No previous run is available '
                    'yet, run NICE once to allow warm starting.">Warm start</span>'
                ),
                self.communicator.param.converged,
            ),
            margin=(15, 0, 2, 10),
        )
        run_msg = "Restore a previous converged NICE run"
        run_label = pn.pane.HTML(
            f'<span title="{run_msg}">Previous run</span>', margin=(15, 0, 2, 10)
        )
        settings_modal = SettingsModal(self.nice_plotter)
        waveform_sync = WaveformSync(main_gui, self.communicator)
        self.collapse_plot = pn.widgets.ToggleIcon(
            icon="layout-sidebar-left-collapse",
            active_icon="layout-sidebar-left-expand",
            description="Collapse the plot to make room for the settings",
            size="24px",
            margin=(15, 10, 2, 10),
        )
        buttons = pn.FlexBox(
            self.collapse_plot,
            settings_modal,
            waveform_sync,
            nice_mode_radio,
            pn.Row(warm_start_label, warm_start_switch, align="center", margin=0),
            pn.Row(run_label, self.run_select, align="center", margin=0),
            button_stop,
            button_start,
            flex_wrap="wrap",
            align_items="center",
            sizing_mode="stretch_width",
        )

        self.metrics = Metrics(max_width=self.nice_plotter.param.frame_width.rx() + 200)
        self.nice_settings.param.watch(self._update_machine_metrics, "machine_preset")
        self._update_machine_metrics()
        self._active_tab = 0
        options = pn.bind(
            self._create_options_tabs,
            self.nice_settings.param.is_inverse_mode,
            self.plasma_shape.param.has_shape,
            self.plasma_properties.param.has_properties,
        )
        menu = pn.Column(buttons, self.terminal, sizing_mode="stretch_width")

        left_col = pn.Column(
            self.nice_plotter.flux_map_pane,
            self.metrics,
            sizing_mode="stretch_height",
            scroll=True,
            visible=self.collapse_plot.param.value.rx.not_(),
        )

        # Drag to make the plot wider or narrower
        plot_handle = DragHandle(
            width=8,
            sizing_mode="stretch_height",
            visible=self.collapse_plot.param.value.rx.not_(),
        )
        plot_handle.param.watch(self._resize_plot, "dx")
        self.nice_plotter.param.watch(
            lambda event: self._limit_drag(plot_handle), "frame_width"
        )
        self._limit_drag(plot_handle)

        self.panel = pn.Row(
            left_col,
            plot_handle,
            pn.Column(
                menu,
                options,
                sizing_mode="stretch_both",
                scroll=True,
            ),
            sizing_mode="stretch_both",
        )

    def _resize_plot(self, event):
        """Resize the plot by how far its handle was dragged"""
        if event.new:
            self.nice_plotter.resize(event.new)
            event.obj.dx = 0

    def _limit_drag(self, handle):
        """Let the handle go only as far as the plot can be resized."""
        handle.min_dx, handle.max_dx = self.nice_plotter.drag_range()

    def _create_options_tabs(self, is_inverse_mode, has_shape, has_properties):
        """Create the tabs holding the inputs for a run.

        Args:
            is_inverse_mode: Whether NICE runs in inverse mode, which is the only
                mode that takes a plasma shape.
            has_shape: Whether a plasma shape is given, which warns in its title.
            has_properties: Whether the plasma properties are given.
        """
        items = []
        if is_inverse_mode:
            items.append(
                (_reactive_title("Plasma Shape", has_shape), self.plasma_shape)
            )
        # The profiles plot is part of the plasma properties panel itself
        items.append(
            (
                _reactive_title("Plasma Properties", has_properties),
                self.plasma_properties,
            )
        )
        items.append(("Coil Currents", self.coil_currents))
        tabs = pn.Tabs(
            *items,
            dynamic=True,
            sizing_mode="stretch_width",
            stylesheets=[".bk-tab { flex: 1; text-align: center; }"],
        )
        tabs.active = min(self._active_tab, len(items) - 1)
        tabs.param.watch(self._remember_active_tab, "active")
        return tabs

    def _remember_active_tab(self, event):
        """Keep the open tab open when the tabs are rebuilt."""
        self._active_tab = event.new

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
    def _reset_run_history(self):
        """Drop the runs, since they are of another machine description now."""
        self.use_previous_run = False
        self.communicator.converged = False
        self.run_history = []
        self.run_select.options = {}
        self.run_select.disabled = True

    def _add_to_history(self):
        """Store the result of the last run in the run history."""
        label = (
            f"Run {len(self.run_history) + 1}: {self.nice_settings.mode} "
            f"({datetime.now():%H:%M:%S})"
        )
        self.run_history.append(
            (label, self.communicator.equilibrium, self.communicator.pf_active)
        )
        self.run_select.options = {
            name: i for i, (name, _, _) in reversed(list(enumerate(self.run_history)))
        }
        self.run_select.value = len(self.run_history) - 1
        self.run_select.disabled = False

    def _restore_run(self, event):
        """Restore the equilibrium and coil currents of the selected run."""
        if event.new is None:
            return
        _, equilibrium, pf_active = self.run_history[event.new]
        self.communicator.equilibrium = equilibrium
        self.communicator.pf_active = pf_active
        self.coil_currents.sync_ui_with_pf_active(pf_active)
        self._update_metrics()
        if self.nice_settings.is_direct_mode:
            self.use_previous_run = True

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
        self.nice_plotter.pf_passive = self.pf_passive
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
        self.nice_plotter.iron_core = self.iron_core
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
            # Show the gaps of the result, which the desired gaps were a target for
            if self.nice_plotter.show_gaps:
                self.nice_plotter.show_result_gaps = True
                self.nice_plotter.show_desired_gaps = False
        else:
            pn.state.notifications.error(
                "NICE did not converge. Check the terminal for details."
            )

    def _has_valid_boundary(self):
        """Check that the desired boundary fits in the fixed size array NICE reads it
        into.

        Returns:
            True if the boundary can be passed to NICE, False otherwise.
        """
        outline = self.plasma_shape.outline_r
        if not self.nice_settings.is_inverse_mode or outline is None:
            return True
        if len(outline) <= MAX_BOUNDARY_POINTS:
            return True

        pn.state.notifications.error(
            f"The plasma boundary has {len(outline)} points, more than the "
            f"{MAX_BOUNDARY_POINTS} NICE accepts. Weighted points are repeated in the "
            "boundary, so lower the max weight or the spread."
        )
        return False

    def _apply_xml_parameters(self, xml_params):
        """Set the parameters configured in the settings on the XML, in place.

        Args:
            xml_params: XML representing configuration parameters.

        Returns:
            True if every configured parameter exists in the XML, False otherwise.
        """
        for name, value in self.nice_settings.xml_parameters.items():
            parameter = xml_params.find(name)
            if parameter is None:
                pn.state.notifications.error(
                    f"NICE has no parameter {name!r}. Check the NICE parameters in "
                    "the settings."
                )
                return False
            parameter.text = str(value)
        return True

    async def submit(self, event=None):
        """Submit a new equilibrium reconstruction job to NICE, passing the machine
        description IDSs and an input equilibrium IDS."""

        if not self._has_valid_boundary():
            return

        self.coil_currents.fill_pf_active(self.pf_active)
        xml_params = ET.fromstring(self.xml_text)
        self.coil_currents.write_coil_groups(xml_params)
        if not self._apply_xml_parameters(xml_params):
            return

        set_xml_parameter(
            xml_params, "algoMode", 11 if self.nice_settings.is_direct_mode else 31
        )
        use_previous_equilibrium = self.use_previous_run and self.communicator.converged
        if self.nice_settings.is_direct_mode:
            start_from_scratch = 0 if use_previous_equilibrium else 1
            set_xml_parameter(xml_params, "algoStartFromScratch", start_from_scratch)
            set_xml_parameter(
                xml_params, "algoStartFromScratchReconAB", start_from_scratch
            )
            set_xml_parameter(
                xml_params,
                "algoStartPsiFromInData",
                1 if use_previous_equilibrium else 0,
            )
        else:
            self.coil_currents.update_xml(xml_params)
        if use_previous_equilibrium:
            pn.state.notifications.info("Starting from previous equilibrium.")
            # Copy, so the stored result in the run history is not modified
            equilibrium = copy.deepcopy(self.communicator.equilibrium)
        else:
            equilibrium = self._create_equilibrium()
        self._fill_equilibrium(equilibrium)

        previous_equilibrium = self.communicator.equilibrium
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
        # Only a converged run is worth restoring
        if (
            self.communicator.equilibrium is not previous_equilibrium
            and self.communicator.converged
        ):
            self._add_to_history()

    def _update_machine_metrics(self, event=None):
        """Show the gaps of the machine of the selected preset"""
        gaps = MACHINE_GAPS.get(self.nice_settings.machine_preset)
        self.metrics.machine_metrics = gaps.GAP_METADATA if gaps else {}

    def _machine_gaps(self, time_slice):
        """The gaps of the machine of the selected preset."""
        gaps = MACHINE_GAPS.get(self.nice_settings.machine_preset)
        if gaps is None:
            return {}
        return {
            name: value * 100 if gaps.GAP_METADATA[name][1] == "cm" else value
            for name, value in gaps.compute_gaps(**gaps.gap_inputs(time_slice)).items()
            if value is not None
        }

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
            **self._machine_gaps(eq.time_slice[0]),
        }

    @param.depends("nice_settings.mode", watch=True)
    def _enable_warm_start_on_direct_mode(self):
        """Warm start direct mode from the last run, if it converged. After a run that
        did not, an earlier one can be picked from the previous runs."""
        if self.nice_settings.is_direct_mode and self.communicator.converged:
            self.use_previous_run = True

    @param.depends(
        "nice_settings.mode",
        "nice_settings.md_pf_active.uri",
        "nice_settings.md_pf_passive.uri",
        "nice_settings.md_wall.uri",
        "nice_settings.md_iron_core.uri",
        watch=True,
    )
    async def stop_nice(self, event=None):
        logger.info("Stopping NICE...")
        await self.communicator.close()

    def __panel__(self):
        return self.panel
