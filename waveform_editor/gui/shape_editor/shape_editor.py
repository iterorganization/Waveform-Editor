import asyncio
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
from waveform_editor.shape_editor.flux import has_flux_map
from waveform_editor.shape_editor.gaps import MACHINE_GAPS
from waveform_editor.shape_editor.nice_integration import NiceIntegration, Start
from waveform_editor.shape_editor.plasma_shape_calc import (
    outline_distances,
    outline_metrics,
)

logger = logging.getLogger(__name__)

# NICE reads the target boundary into an array of this fixed size
# (MAX_PLASMA_BOUNDARY_POINTS in its solver_structs.h)
MAX_BOUNDARY_POINTS = 5000


def _reactive_title(title, is_valid):
    return title if is_valid else f"{title} ⚠️"


class ShapeEditor(Viewer):
    MAX_LOG_LINES = 10000
    # Pixels below the top of the plot that are not its frame, of its axis
    BELOW_PLOT = 80
    # Seconds the inputs must be unchanged before auto run runs NICE again
    AUTO_RUN_DELAY = 0.3

    nice_settings = param.ClassSelector(class_=NiceSettings)
    plasma_shape = param.ClassSelector(class_=PlasmaShape)
    plasma_properties = param.ClassSelector(class_=PlasmaProperties)
    auto_run = param.Boolean(doc="Run NICE whenever its inputs change")

    pf_active = param.ClassSelector(class_=IDSToplevel)
    pf_passive = param.ClassSelector(class_=IDSToplevel)
    wall = param.ClassSelector(class_=IDSToplevel)
    iron_core = param.ClassSelector(class_=IDSToplevel)
    tf = param.ClassSelector(class_=IDSToplevel)

    def __init__(self, main_gui):
        super().__init__()
        self.factory = imas.IDSFactory()
        self.terminal = pn.widgets.Terminal(
            sizing_mode="stretch_both",
            options={"scrollback": self.MAX_LOG_LINES, "wrap": True},
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
        # Only a converged result can be a reference shape
        self.communicator.param.watch(
            lambda *events: self.plasma_shape.param.update(
                last_result=self.communicator.equilibrium
                if self.communicator.converged
                else None
            ),
            ["equilibrium", "converged"],
        )
        self.plasma_properties.param.watch(self._scale_coil_currents, "ip")
        self.nice_plotter = NicePlotter(
            communicator=self.communicator,
            plasma_shape=self.plasma_shape,
            plasma_properties=self.plasma_properties,
        )
        self.metrics = Metrics()
        # Converged runs as (label, equilibrium, pf_active) tuples, oldest first
        self.run_history = []
        # Whether auto run is running NICE, and whether the inputs changed since
        self._submitting = False
        self._inputs_changed = False
        self.run_select = pn.widgets.Select(
            options={},
            disabled=True,
            width=260,
            margin=(10, 0, 2, 10),
        )
        self.run_select.param.watch(self._restore_run, "value")
        self.nice_settings = settings.nice
        for md in self.nice_settings.machine_descriptions:
            md.param.watch(self._load_machine_description, "uri")
            md.param.trigger("uri")

        self.xml_text = (
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("param.xml")
            .read_text()
        )

        # UI Configuration
        self._cannot_run = (
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
                lambda cannot_run, auto_run: (
                    "Disabled while auto run is on"
                    if auto_run
                    else "Cannot run: missing required inputs"
                    if cannot_run
                    else "Run simulation"
                ),
                self._cannot_run,
                self.param.auto_run,
            ),
            disabled=self._cannot_run | self.param.auto_run.rx(),
            margin=(10, 0, 2, 0),
        )
        auto_run_label = pn.pane.HTML(
            '<span title="Run NICE whenever the plasma shape, plasma properties or '
            "coil currents change. The latest converged auto run is kept in the "
            'run history.">Auto run</span>',
            margin=(15, 0, 2, 10),
        )
        auto_run_switch = pn.widgets.Switch.from_param(
            self.param.auto_run, name="", margin=(20, 15, 2, 10)
        )
        button_stop = pn.widgets.Button(
            name="Stop",
            button_type="danger",
            icon="player-stop",
            on_click=self.stop_nice,
            margin=(10, 10, 2, 0),
        )
        nice_mode_radio = nice_mode_toggle(self.nice_settings, margin=(10, 0, 2, 0))
        run_msg = "Restore a previous converged NICE run"
        run_label = pn.pane.HTML(
            f'<span title="{run_msg}">Run history</span>', margin=(15, 0, 2, 10)
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
            pn.Row(run_label, self.run_select, align="center", margin=0),
            pn.Row(
                auto_run_label,
                auto_run_switch,
                button_stop,
                button_start,
                align="center",
                margin=0,
                styles={"margin-left": "auto"},
            ),
            flex_wrap="wrap",
            align_items="center",
            sizing_mode="stretch_width",
        )

        self.nice_settings.param.watch(self._update_machine_metrics, "machine_preset")
        self._update_machine_metrics()
        self.plasma_shape.param.watch(self._update_target_metrics, "redraw")
        self.nice_settings.param.watch(
            self._update_target_metrics, ["mode", "machine_preset"]
        )
        for obj, name in (
            (self, "auto_run"),
            (self.plasma_shape, "shape_updated"),
            (self.plasma_properties, "profile_updated"),
            (self.coil_currents, "edited"),
        ):
            obj.param.watch(self._auto_submit, name)
        self._active_tab = 0
        options = pn.bind(
            self._create_options_tabs,
            self.nice_settings.param.is_inverse_mode,
            self.plasma_properties.param.has_properties,
        )
        left_col = pn.Column(
            self.nice_plotter.flux_map_pane,
            self.nice_plotter.legend,
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
        plot_handle.param.watch(self._fit_plot, "room")
        self.nice_plotter.param.watch(
            lambda event: self._limit_drag(plot_handle), "frame_width"
        )
        self._limit_drag(plot_handle)

        self.panel = pn.Row(
            left_col,
            plot_handle,
            pn.Column(
                buttons,
                options,
                self.terminal,
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

    def _fit_plot(self, event):
        """Make the plot as large as the browser window has room for, beside the
        inputs."""
        right, below = event.new
        plot = self.nice_plotter
        # The handle moves with the right of the plot, as far as it widens
        plot.fit(
            plot.frame_width + right - event.obj.min_right, below - self.BELOW_PLOT
        )

    def _limit_drag(self, handle):
        """Let the handle go only as far as the plot can be resized."""
        handle.min_dx, handle.max_dx = self.nice_plotter.drag_range()

    def _create_options_tabs(self, is_inverse_mode, has_properties):
        """Create the tabs holding the inputs for a run.

        Args:
            is_inverse_mode: Whether NICE runs in inverse mode, which is the only
                mode that takes a plasma shape.
            has_properties: Whether the plasma properties are given.
        """
        items = []
        if is_inverse_mode:
            shape_tab = pn.Column(
                self.plasma_shape,
                pn.Column(
                    self.metrics,
                    margin=(0, 20, 12, 20),
                    # Out of the way while a reference shape is chosen
                    visible=self.plasma_shape.param.reference_source.rx()
                    == PlasmaShape.SOURCE_NONE,
                ),
                margin=0,
            )
            # No warning in its title for a missing shape, which would rebuild all
            # tabs, flashing them, whenever a reference shape is set
            items.append(("Plasma Shape", shape_tab))
        # The profiles plot is part of the plasma properties panel itself
        items.append(
            (
                _reactive_title("Plasma Properties", has_properties),
                self.plasma_properties,
            )
        )
        items.append(("Coil Currents", self.coil_currents))
        # The log is shown below the tabs, so that it is not rendered again, which
        # would lose its output: https://github.com/holoviz/panel/issues/8832
        items.append(("Logging", pn.Spacer(height=0)))
        log_tab = len(items) - 1
        # Without a margin, as hidden tabs still take up the margin of their content
        tabs = pn.Tabs(
            *(
                (title, pn.Column(content, margin=0, sizing_mode="stretch_width"))
                for title, content in items
            ),
            dynamic=True,
            sizing_mode="stretch_width",
            stylesheets=[".bk-tab { flex: 1; text-align: center; }"],
        )
        # Without the plasma shape tab, the other tabs move one to the left
        tabs.active = max(self._active_tab - (not is_inverse_mode), 0)
        tabs.param.watch(self._remember_active_tab, "active")
        self.terminal.visible = tabs.param.active.rx() == log_tab
        return tabs

    def _remember_active_tab(self, event):
        """Keep the open tab open when the tabs are rebuilt."""
        self._active_tab = event.new + (not self.nice_settings.is_inverse_mode)

    def _scale_coil_currents(self, event):
        """Scale the coil currents with the plasma current, when that is enabled."""
        if self.plasma_properties.scale_coil_currents:
            self.coil_currents.scale_to_ip(event.new)

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
    def _clear_results(self):
        """Drop the result and the runs, since they are of another machine description
        now."""
        self.communicator.param.update(equilibrium=None, pf_active=None)
        self.metrics.result = {}
        self.run_history = []
        self.run_select.options = {}
        self.run_select.disabled = True

    def _add_to_history(self, auto=False):
        """Store the result of the last run in the run history. That of an auto run
        replaces that of the auto run right before it.

        Args:
            auto: Whether the run is an auto run.
        """
        if auto and self.run_history and self.run_history[-1][0].startswith("Auto"):
            self.run_history.pop()
        label = (
            f"{'Auto run' if auto else 'Run'} {len(self.run_history) + 1}: "
            f"{self.nice_settings.mode} ({datetime.now():%H:%M:%S})"
        )
        self.run_history.append(
            (label, self.communicator.equilibrium, self.communicator.pf_active)
        )
        self._list_runs()
        self.run_select.value = len(self.run_history) - 1
        self.run_select.disabled = False

    def _list_runs(self, unsaved=None):
        """List the runs in the run history, newest first.

        Args:
            unsaved: The label of the result shown, if it is not kept, to list on top
                so that any run in the history can be selected to return to it.
        """
        runs = {
            name: i for i, (name, _, _) in reversed(list(enumerate(self.run_history)))
        }
        self.run_select.options = {unsaved: None, **runs} if unsaved else runs

    def _restore_run(self, event):
        """Restore the equilibrium and coil currents of the selected run, unless it
        is shown already, as a new run is when it is added."""
        if event.new is None:
            return
        _, equilibrium, pf_active = self.run_history[event.new]
        if equilibrium is self.communicator.equilibrium:
            return
        self.communicator.param.update(equilibrium=equilibrium, pf_active=pf_active)
        self.coil_currents.sync_ui_with_pf_active(
            pf_active, equilibrium.time_slice[0].global_quantities.ip
        )
        self._update_metrics()
        self._list_runs()

    def _load_machine_description(self, event):
        """Load a machine description into the parameter of its IDS name, and into
        that of the components that use it."""
        md = event.obj
        ids = self._load_slice(md.uri, md.ids_name)
        self.param.update({md.ids_name: ids})
        for component in (self.nice_plotter, self.plasma_properties):
            if md.ids_name in component.param:
                component.param.update({md.ids_name: ids})
        if md.ids_name == "pf_active":
            self.coil_currents.create_ui(ids)
        md.loaded = ids is not None

    def _iron_core_or_empty(self):
        """The iron_core to send to NICE, an empty one for a machine without."""
        if self.iron_core is not None:
            return self.iron_core
        iron_core = self.factory.new("iron_core")
        iron_core.ids_properties.homogeneous_time = (
            imas.ids_defs.IDS_TIME_MODE_INDEPENDENT
        )
        return iron_core

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
        problem = self._result_problem() if success else ""
        if success and not problem:
            # Show the gaps of the result, instead of the target gaps
            if self.nice_plotter.show_gaps:
                self.nice_plotter.show_result_gaps = True
                self.nice_plotter.show_target_gaps = False
            return
        self.communicator.converged = False
        pn.state.notifications.error(
            f"NICE did not converge{problem}. Check the Logging tab for details."
        )

    def _result_problem(self):
        """Why the result of a run NICE says converged is wrong, empty if it is not:
        it has no poloidal flux, or it misses the target shape of an inverse run by
        more than a quarter of its minor radius, as when NICE converges to a plasma
        elsewhere."""
        time_slice = self.communicator.equilibrium.time_slice[0]
        if not has_flux_map(time_slice):
            return ": it gave no poloidal flux"
        shape = self.plasma_shape
        if self.nice_settings.is_direct_mode or not shape.has_shape:
            return ""
        outline = time_slice.boundary.outline
        if len(outline.r) < 3:
            return ": its result has no boundary"
        distance = outline_distances(
            shape.outline_r, shape.outline_z, outline.r, outline.z
        ).max()
        minor_radius = (max(shape.outline_r) - min(shape.outline_r)) / 2
        if distance < minor_radius / 4:
            return ""
        return f": its result misses the target shape by up to {distance:.2f} m"

    def _has_valid_boundary(self):
        """Check that the target boundary fits in the fixed size array NICE reads it
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
        """Run NICE once, while auto run is off."""
        await self._run_nice(auto=False)

    async def _auto_submit(self, event=None):
        """Run NICE on a change of its inputs, while auto run is on. Changes made
        during a run are run together once they have settled.
        """
        if not self.auto_run:
            return
        self._inputs_changed = True
        if self._submitting:
            return
        self._submitting = True
        try:
            settled = True
            while self._inputs_changed and self.auto_run:
                self._inputs_changed = False
                if not settled:
                    await asyncio.sleep(self.AUTO_RUN_DELAY)
                    settled = not self._inputs_changed
                if settled and not self._cannot_run.rx.value:
                    await self._run_nice(auto=True)
                    settled = False
        finally:
            self._submitting = False

    async def _run_nice(self, auto):
        """Submit a new equilibrium reconstruction job to NICE, passing the machine
        description IDSs and an input equilibrium IDS.

        Args:
            auto: Whether the run is an auto run.
        """

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
        start = self.communicator.start_mode(self.nice_settings.is_direct_mode)
        start_from_scratch = int(start is Start.SCRATCH)
        set_xml_parameter(xml_params, "algoStartFromScratch", start_from_scratch)
        set_xml_parameter(
            xml_params, "algoStartPsiFromInData", int(start is Start.DATA)
        )
        if self.nice_settings.is_direct_mode:
            set_xml_parameter(
                xml_params, "algoStartFromScratchReconAB", start_from_scratch
            )
        else:
            self.coil_currents.update_xml(xml_params)
        if start is not Start.SCRATCH and not auto:
            pn.state.notifications.info("Starting from previous equilibrium.")
        if start is Start.DATA:
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
            self._iron_core_or_empty().serialize(),
        )
        # NICE crashed without a result
        if self.communicator.equilibrium is previous_equilibrium:
            return
        self.coil_currents.sync_ui_with_pf_active(
            self.communicator.pf_active, self.plasma_properties.ip
        )
        self._update_metrics()
        # Only a converged run is worth restoring
        if self.communicator.converged:
            if not auto:
                pn.state.notifications.success("NICE run complete.")
            self._add_to_history(auto)
        elif self.run_history:
            self._list_runs(unsaved="Not converged")
            self.run_select.value = None

    def _update_machine_metrics(self, event=None):
        """Show the gaps of the machine of the selected preset"""
        gaps = MACHINE_GAPS.get(self.nice_settings.machine_preset)
        self.metrics.machine_metrics = gaps.GAP_METADATA if gaps else {}

    def _machine_gaps(self, time_slice):
        """The gaps of the machine of the selected preset."""
        gaps = MACHINE_GAPS.get(self.nice_settings.machine_preset)
        if gaps is None:
            return {}
        return gaps.compute_gaps(**gaps.gap_inputs(time_slice))

    def _update_target_metrics(self, *events):
        """Show the shape of the target, if there is one drawn."""
        shape = self.plasma_shape
        if not self.nice_plotter.has_target():
            self.metrics.target = {}
            return
        # The boundary itself, without the extra points
        r, z = (
            (shape.param_r, shape.param_z)
            if shape.param_r is not None
            else (shape.outline_r, shape.outline_z)
        )
        # Free points being placed may not span a width to measure a shape by yet
        target = outline_metrics(r, z) if max(r) > min(r) else {}
        gaps = MACHINE_GAPS.get(self.nice_settings.machine_preset)
        if gaps is not None:
            inputs = gaps.shape_inputs(shape.target_x_points)
            target.update(gaps.compute_gaps(shape.outline_r, shape.outline_z, **inputs))
        self.metrics.target = target

    def _update_metrics(self):
        if not self.communicator.converged:
            self.metrics.result = {}  # the shape of a run that did not converge
            return
        eq = self.communicator.equilibrium
        global_quantities = eq.time_slice[0].global_quantities
        boundary = eq.time_slice[0].boundary

        self.metrics.result = {
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
        self._inputs_changed = False
        await self.communicator.close()

    def __panel__(self):
        return self.panel
