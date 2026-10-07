import logging

import holoviews as hv
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import panel as pn
import param
import scipy.interpolate as interp
from bokeh.models import HoverTool, PointDrawTool
from imas.ids_toplevel import IDSToplevel
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.plasma_properties import PlasmaProperties
from waveform_editor.gui.shape_editor.plasma_shape import PlasmaShape
from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration

matplotlib.use("Agg")
logger = logging.getLogger(__name__)


def _no_hover(element):
    """Exclude an element's renderer from every HoverTool in the shared figure."""

    def hook(plot, _):
        renderer = plot.handles.get("glyph_renderer")
        for tool in plot.state.toolbar.tools:
            if isinstance(tool, HoverTool) and renderer in (tool.renderers or []):
                tool.renderers = [r for r in tool.renderers if r is not renderer]

    return element.opts(hooks=[hook])


def _element_outline(geometry, name):
    """The corners of an element of a machine, whichever way it is described.

    Args:
        geometry: An ``outline_2d_geometry_static`` structure, such as
            ``pf_passive/loop/element/geometry`` or ``iron_core/segment/geometry``.
            Its outline, rectangle or oblique is drawn.
        name: The name of the element, for the warning when it cannot be outlined.

    Returns:
        Tuple of (r, z) of a closed outline, which is empty if it cannot be outlined.
    """
    if geometry.outline.has_value:
        return geometry.outline.r, geometry.outline.z
    rectangle = geometry.rectangle
    if rectangle.has_value:
        r, z = rectangle.r, rectangle.z
        dr, dz = rectangle.width / 2, rectangle.height / 2
        return (
            np.array([r - dr, r + dr, r + dr, r - dr, r - dr]),
            np.array([z - dz, z - dz, z + dz, z + dz, z - dz]),
        )
    oblique = geometry.oblique
    if oblique.has_value:
        # Two sides from a corner, each at its own angle
        dr_a = oblique.length_alpha * np.cos(oblique.alpha)
        dz_a = oblique.length_alpha * np.sin(oblique.alpha)
        dr_b = -oblique.length_beta * np.sin(oblique.beta)
        dz_b = oblique.length_beta * np.cos(oblique.beta)
        r, z = oblique.r, oblique.z
        return (
            np.array([r, r + dr_a, r + dr_a + dr_b, r + dr_b, r]),
            np.array([z, z + dz_a, z + dz_a + dz_b, z + dz_b, z]),
        )
    logger.warning(
        f"{str(name)!r} is skipped, as it has no outline, rectangle or oblique"
    )
    return [], []


def _geometry_paths(paths, color="black", line_width=2):
    """Paths of the outlines of parts of a machine, named on hover.

    Args:
        paths: List of (r, z, name) of each outline.
        color: Colour of the lines.
        line_width: Width of the lines.
    """
    return hv.Path(paths, vdims=["name"]).opts(
        color=color,
        line_width=line_width,
        show_legend=False,
        hover_tooltips=[("", "@name")],
    )


class NicePlotter(Viewer):
    # Input data, use negative precedence to hide from the UI
    communicator = param.ClassSelector(class_=NiceIntegration, precedence=-1)
    wall = param.ClassSelector(class_=IDSToplevel, precedence=-1)
    pf_active = param.ClassSelector(class_=IDSToplevel, precedence=-1)
    pf_passive = param.ClassSelector(class_=IDSToplevel, precedence=-1)
    iron_core = param.ClassSelector(class_=IDSToplevel, precedence=-1)
    plasma_shape = param.ClassSelector(class_=PlasmaShape, precedence=-1)
    plasma_properties = param.ClassSelector(class_=PlasmaProperties, precedence=-1)
    nice_settings = param.ClassSelector(class_=NiceSettings, precedence=-1)

    # Plot parameters
    show_contour = param.Boolean(default=True, label="Show contour lines")
    levels = param.Integer(
        default=20, bounds=(1, 200), label="Number of contour levels"
    )
    show_heatmap = param.Boolean(default=False, label="Show heatmap")
    heatmap_alpha = param.Number(
        default=0.7, bounds=(0.0, 1.0), step=0.05, label="Heatmap opacity"
    )
    show_coils = param.Boolean(default=True, label="Show coils")
    show_wall = param.Boolean(default=True, label="Show limiter and divertor")
    show_vacuum_vessel = param.Boolean(
        default=True, label="Show inner and outer vacuum vessel"
    )
    show_passive_structures = param.Boolean(
        default=True, label="Show passive structures"
    )
    show_iron_core = param.Boolean(default=True, label="Show iron core")
    show_plasma_facing_components = param.Boolean(
        default=True, label="Show plasma facing components"
    )
    show_xo = param.Boolean(default=True, label="Show x-point and o-point")
    show_separatrix = param.Boolean(default=True, label="Show separatrix")
    show_desired_shape = param.Boolean(default=True, label="Show desired shape")

    # Renderer of the editable points, set once the plot is first rendered
    _points_renderer = None
    _points_toolbar = None
    _syncing_points = False

    # Bokeh cannot hold the aspect of the machine while it resizes, so the plot has a
    # fixed size, which is changed by dragging the handle beside it
    frame_height = param.Integer(
        default=700, bounds=(100, 1600), precedence=-1, doc="Height of the plot"
    )
    frame_width = param.Integer(
        precedence=-1, doc="Width of the plot, following its height and machine"
    )
    # The r and z range to plot per machine, wide enough to hold its coils
    MACHINE_RANGES = {
        NiceSettings.PRESET_ITER: ((0, 13), (-10, 10)),
        NiceSettings.PRESET_WEST: ((0, 4.8), (-2.6, 2.6)),
    }
    R_RANGE, Z_RANGE = MACHINE_RANGES[NiceSettings.PRESET_ITER]
    HEATMAP_RESOLUTION = 250

    def __init__(self, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice
        self._figure = None
        self.nice_settings.param.watch(self._apply_machine_ranges, "machine_preset")
        r_range, z_range = self._machine_ranges()
        self.frame_width = self._width_for(self.frame_height)
        self.DEFAULT_OPTS = hv.opts.Overlay(
            xlim=r_range,
            ylim=z_range,
            frame_width=self.frame_width,
            frame_height=self.frame_height,
            title="",
            xlabel="r [m]",
            ylabel="z [m]",
            fontsize={"labels": 15, "ticks": 11},
            hooks=[self._capture_figure],
        )
        self.CONTOUR_OPTS = hv.opts.Contours(
            cmap="viridis",
            colorbar=True,
            tools=["hover"],
            colorbar_opts={"title": "Poloidal flux [Wb]"},
            show_legend=False,
        )
        self.CONTOUR_ON_HEATMAP_OPTS = hv.opts.Contours(
            color="white",
            alpha=0.6,
            line_width=1,
            colorbar=False,
            tools=["hover"],
            show_legend=False,
        )
        self._heatmap_cache = (None, None)
        self.HEATMAP_OPTS = hv.opts.Image(
            cmap="viridis",
            colorbar=True,
            tools=["hover"],
            hover_tooltips=[
                ("r", "$x{0.00} m"),
                ("z", "$y{0.00} m"),
                ("psi", "@image{0.000} Wb"),
            ],
            colorbar_opts={"title": "Poloidal flux [Wb]"},
            show_legend=False,
        )
        self.DESIRED_SHAPE_OPTS = hv.opts.Curve(color="blue")
        # Static on purpose. The draw tool binds to this element's renderer, and
        # redrawing it either breaks the binding or feeds edits back into redraws.
        self.editable_points = hv.Points([], kdims=["r", "z"], vdims=["weight"]).opts(
            color="blue",
            size=8,
            marker="o",
            show_legend=False,
            hooks=[self._capture_points_renderer],
        )
        flux_map_elements = [
            hv.DynamicMap(self._plot_heatmap),
            hv.DynamicMap(self._plot_contours),
            hv.DynamicMap(self._plot_separatrix),
            hv.DynamicMap(self._plot_xo_points),
            hv.DynamicMap(self._plot_coil_rectangles),
            hv.DynamicMap(self._plot_wall),
            hv.DynamicMap(self._plot_components),
            hv.DynamicMap(self._plot_vacuum_vessel),
            hv.DynamicMap(self._plot_passive_structures),
            hv.DynamicMap(self._plot_iron_core),
            hv.DynamicMap(self._plot_plasma_shape),
            self.editable_points,
        ]
        # Lets the weighted points be added, dragged and deleted on the plot
        self.point_draw = hv.streams.PointDraw(
            source=self.editable_points, drag=True, add=True, empty_value=1
        )
        self.point_draw.add_subscriber(self._on_point_draw)

        flux_map_overlay = (
            hv.Overlay(flux_map_elements).collate().opts(self.DEFAULT_OPTS)
        )
        self.flux_map_pane = pn.pane.HoloViews(
            flux_map_overlay,
            loading=self.communicator.param.processing,
        )

        self.plasma_shape.param.watch(self._update_points_visibility, "input_mode")
        self.plasma_shape.shape_params.param.watch(
            self._update_points_visibility, "extra_points_enabled"
        )
        self.nice_settings.param.watch(self._update_points_visibility, "mode")
        self.plasma_shape.weighted_points_table.param.watch(
            self._push_points_to_plot, "points"
        )

        self.panel_layout = pn.Param(
            self.param,
            show_name=False,
            widgets={
                "show_desired_shape": {
                    "visible": self.nice_settings.param.is_inverse_mode
                }
            },
        )

    def _uses_weighted_points(self):
        """Whether the weighted points table is in use for the current input mode."""
        return (
            not self.nice_settings.is_direct_mode
            and self.plasma_shape.uses_weighted_points
        )

    def _capture_points_renderer(self, plot, element):
        """Keep hold of the renderer and the toolbar, so the points can be hidden
        without redrawing them, which would break the draw tool."""
        self._points_renderer = plot.handles.get("glyph_renderer")
        self._points_toolbar = plot.state.toolbar
        self._update_points_visibility()

    def _update_points_visibility(self, *events):
        """Only show the points, and offer the tool to draw them, while they are in
        use. The tool is selected right away, since drawing points is the only reason
        to turn them on."""
        if self._points_renderer is None:
            return
        in_use = self._uses_weighted_points()
        self._points_renderer.visible = in_use
        toolbar = self._points_toolbar
        for tool in toolbar.tools:
            if isinstance(tool, PointDrawTool):
                tool.visible = in_use
                toolbar.active_tap = tool if in_use else "auto"

    def _push_points_to_plot(self, *events):
        """Mirror the table onto the plot, for rows edited or deleted in the table.

        The points are written straight into the renderer rather than redrawn,
        because redrawing them would break the draw tool.
        """
        # The plot already shows the points it just handed us
        if self._points_renderer is None or self._syncing_points:
            return
        r, z, weights = self.plasma_shape.weighted_points_table.get_points()
        data = {"r": r, "z": z, "weight": weights}

        def apply():
            self._syncing_points = True
            try:
                self._points_renderer.data_source.data = data
            finally:
                self._syncing_points = False

        # Scheduled, so that the document lock is held while the model is changed
        pn.state.execute(apply)

    def _on_point_draw(self, data):
        """Write points added, dragged or deleted on the plot back to the table."""
        if not data or self._syncing_points or not self._uses_weighted_points():
            return
        r, z, weights = data["r"], data["z"], data["weight"]
        self._syncing_points = True
        try:
            self.plasma_shape.weighted_points_table.set_points(r, z, weights)
        finally:
            self._syncing_points = False

    def _capture_figure(self, plot, element):
        """Keep hold of the figure, so its ranges can follow the machine preset."""
        self._figure = plot.state

    def _machine_ranges(self):
        """The r and z range of the machine of the selected preset."""
        return self.MACHINE_RANGES.get(
            self.nice_settings.machine_preset, (self.R_RANGE, self.Z_RANGE)
        )

    def _width_for(self, height):
        """The width of the plot at a height, for the aspect of the machine."""
        (r_min, r_max), (z_min, z_max) = self._machine_ranges()
        return round(height * (r_max - r_min) / (z_max - z_min))

    def resize(self, dx):
        """Widen the plot by a number of pixels, or narrow it if negative, within its
        bounds and keeping the aspect of the machine.

        Args:
            dx: Pixels to change the width of the plot by.
        """
        low, high = self.param.frame_height.bounds
        height = round((self.frame_width + dx) * self.frame_height / self.frame_width)
        self.frame_height = max(low, min(high, height))

    def drag_range(self):
        """How far the plot can be narrowed and widened, in pixels of its width.

        Returns:
            Tuple of the most it can be narrowed, as a negative number, and the most
            it can be widened.
        """
        low, high = self.param.frame_height.bounds
        return self._width_for(low) - self.frame_width, self._width_for(
            high
        ) - self.frame_width

    def _apply_machine_ranges(self, event=None):
        """Show the machine of the selected preset, coils and all."""
        if self._figure is not None:
            r_range, z_range = self._machine_ranges()
            self._figure.x_range.start, self._figure.x_range.end = r_range
            self._figure.y_range.start, self._figure.y_range.end = z_range
        self._resize_figure()

    @param.depends("frame_height", watch=True)
    def _resize_figure(self):
        """Give the figure the size of the plot, without drawing it again, so that a
        zoom is kept."""
        self.frame_width = self._width_for(self.frame_height)
        if self._figure is not None:
            self._figure.frame_width = self.frame_width
            self._figure.frame_height = self.frame_height

    @pn.depends(
        "plasma_shape.shape_updated", "show_desired_shape", "nice_settings.mode"
    )
    def _plot_plasma_shape(self):
        shape = self.plasma_shape
        if (
            self.nice_settings.is_direct_mode
            or not self.show_desired_shape
            or not shape.has_shape
            or shape.input_mode == shape.WEIGHTED_POINTS_INPUT
        ):
            return hv.Overlay([hv.Curve([]).opts(self.DESIRED_SHAPE_OPTS)])

        if shape.input_mode == shape.GAP_INPUT:
            return self._plot_gaps(shape.outline_r, shape.outline_z)

        if shape.input_mode == shape.PARAMETERIZED_INPUT:
            if shape.param_weights is not None:
                return self._plot_weighted_boundary()
            # The parameterized points, so that extra points appended to the outline
            # are not drawn as part of the boundary curve
            return self._plot_outline_shape(shape.param_r, shape.param_z)

        return self._plot_outline_shape(shape.outline_r, shape.outline_z)

    def _plot_outline_shape(self, r, z):
        """Plots closed plasma outline curve.

        Args:
            r: Radial coordinates of the outline.
            z: Height coordinates of the outline.

        Returns:
            Holoviews overlay with the outline curve.
        """
        if r[0] != r[-1] or z[0] != z[-1]:
            r = np.append(r, r[0])
            z = np.append(z, z[0])

        return hv.Overlay([hv.Curve((r, z)).opts(self.DESIRED_SHAPE_OPTS)])

    def _plot_gaps(self, r, z):
        """Plots the reference point, value and the desired boundary point of the gaps.

        Args:
            r: Radial coordinates of the outline.
            z: Height coordinates of the outline.

        Returns:
            Holoviews overlay containing gap representation.
        """
        plot_elements = [_no_hover(hv.Scatter((r, z)).opts(color="blue", size=4))]
        for gap in self.plasma_shape.gaps:
            plot_elements.append(
                _no_hover(hv.Scatter(([gap.r], [gap.z])).opts(color="red", size=6))
            )
            plot_elements.append(
                _no_hover(
                    hv.Segments([(gap.r, gap.z, gap.r_sep, gap.z_sep)]).opts(
                        color="black"
                    )
                )
            )
        return hv.Overlay(plot_elements)

    def _plot_weighted_boundary(self):
        """Plots the parameterized boundary as a curve coloured by each
        point's weight, so the emphasized region is visible at a glance.

        Returns:
            Holoviews overlay with the coloured boundary curve.
        """
        r = self.plasma_shape.param_r
        z = self.plasma_shape.param_z
        weights = self.plasma_shape.param_weights
        n = len(r)

        segments = []
        for i in range(n):
            j = (i + 1) % n
            avg_weight = (weights[i] + weights[j]) / 2
            segments.append((r[i], z[i], r[j], z[j], avg_weight))

        curve = hv.Segments(segments, vdims="weight").opts(
            color="weight",
            cmap="viridis",
            colorbar=True,
            line_width=3,
            show_legend=False,
            colorbar_opts={"title": "Weight"},
        )
        return hv.Overlay([curve])

    @pn.depends("pf_active", "show_coils", "communicator.pf_active")
    def _plot_coil_rectangles(self):
        """Creates rectangular and path overlays for PF coils.

        Returns:
            Coil geometry overlay.
        """
        rectangles = []
        paths = []
        if self.show_coils and self.pf_active is not None:
            for idx, coil in enumerate(self.pf_active.coil):
                name = str(coil.name)
                if self.communicator.pf_active and len(
                    self.communicator.pf_active.coil
                ) == len(self.pf_active.coil):
                    current = self.communicator.pf_active.coil[idx].current.data[0]
                    units = self.communicator.pf_active.coil[idx].current.metadata.units
                    name = f"{name} | {current:.3f} [{units}]"
                for element in coil.element:
                    rect = element.geometry.rectangle
                    outline = element.geometry.outline
                    annulus = element.geometry.annulus
                    if rect.has_value:
                        r0 = rect.r - rect.width / 2
                        r1 = rect.r + rect.width / 2
                        z0 = rect.z - rect.height / 2
                        z1 = rect.z + rect.height / 2
                        rectangles.append((r0, z0, r1, z1, name))
                    elif outline.has_value:
                        paths.append((outline.r, outline.z, name))
                    elif annulus.r.has_value:
                        # Just plot outer radius for now
                        phi = np.linspace(0, 2 * np.pi, 17)
                        paths.append(
                            (
                                (annulus.r + annulus.radius_outer * np.cos(phi)),
                                (annulus.z + annulus.radius_outer * np.sin(phi)),
                                name,
                            )
                        )
                    else:
                        logger.warning(
                            f"Coil {name} was skipped, as it does not have a filled "
                            "'rect' or 'outline' node"
                        )
                        continue
        rects = hv.Rectangles(rectangles, vdims=["name"]).opts(
            line_color="black",
            fill_alpha=0,
            line_width=2,
            show_legend=False,
            hover_tooltips=[("", "@name")],
        )
        return rects * _geometry_paths(paths, line_width=1)

    @pn.depends("communicator.equilibrium", "show_heatmap", "heatmap_alpha")
    def _plot_heatmap(self):
        """Generates heatmap plot for poloidal flux.

        Returns:
            Holoviews Image containing the poloidal flux field.
        """
        equilibrium = self.communicator.equilibrium
        if not self.show_heatmap or equilibrium is None:
            return self._empty_heatmap()

        flux_map = self._flux_map(equilibrium)
        if flux_map is None:
            return self._empty_heatmap()

        if self._heatmap_cache[0] is not equilibrium:
            self._heatmap_cache = (equilibrium, self._calc_heatmap(*flux_map))
        return (
            hv.Image(self._heatmap_cache[1], kdims=["r", "z"], vdims=["psi"])
            .opts(self.HEATMAP_OPTS)
            .opts(alpha=self.heatmap_alpha)
        )

    def _empty_heatmap(self):
        return (
            hv.Image([], kdims=["r", "z"], vdims=["psi"])
            .opts(self.HEATMAP_OPTS)
            .opts(alpha=0.0, colorbar=False)
        )

    def _calc_heatmap(self, r, z, psi):
        """Interpolates psi onto a regular grid for heatmap display.

        Args:
            r: Radial coordinates of the mesh nodes.
            z: Height coordinates of the mesh nodes.
            psi: Poloidal flux values at the mesh nodes.

        Returns:
            Tuple of (grid_r, grid_z, psi_grid).
        """
        r, z = np.asarray(r, dtype=float), np.asarray(z, dtype=float)
        grid_r = np.linspace(r.min(), r.max(), self.HEATMAP_RESOLUTION)
        grid_z = np.linspace(z.min(), z.max(), self.HEATMAP_RESOLUTION)
        psi_grid = interp.griddata(
            (r, z), np.asarray(psi, dtype=float), tuple(np.meshgrid(grid_r, grid_z))
        )
        return grid_r, grid_z, psi_grid

    @pn.depends("communicator.equilibrium", "show_contour", "levels", "show_heatmap")
    def _plot_contours(self):
        """Generates contour plot for poloidal flux.

        Returns:
            Contour plot of psi.
        """
        equilibrium = self.communicator.equilibrium
        if not self.show_contour or equilibrium is None:
            contours = hv.Contours(([0], [0], 0), vdims="psi")
        else:
            contours = self._calc_contours(equilibrium, self.levels)

        return contours.opts(
            self.CONTOUR_ON_HEATMAP_OPTS if self.show_heatmap else self.CONTOUR_OPTS
        )

    def _flux_map(self, equilibrium):
        """The poloidal flux on the GGD that NICE fills.

        Args:
            equilibrium: The equilibrium IDS to read the flux from.

        Returns:
            Tuple of (r, z, psi) at the mesh nodes, or None if NICE did not fill them.
        """
        eqggd = equilibrium.time_slice[0].ggd[0]
        r, z, psi = eqggd.r[0].values, eqggd.z[0].values, eqggd.psi[0].values
        if not r or not z or not psi:
            pn.state.notifications.error(
                "NICE did not produce a valid poloidal flux field"
            )
            return None
        return r, z, psi

    def _calc_contours(self, equilibrium, levels):
        """Calculates the contours of the psi grid of an equilibrium IDS.

        Args:
            equilibrium: The equilibrium IDS to load psi grid from.
            levels: Determines the number of contour lines. Either an integer for total
                number of contour lines, or a list of specified levels.

        Returns:
            Holoviews contours object
        """
        flux_map = self._flux_map(equilibrium)
        if flux_map is None:
            return hv.Contours(([0], [0], 0), vdims="psi")

        trics = plt.tricontour(*flux_map, levels=levels)
        return hv.Contours(self._extract_contour_segments(trics), vdims="psi")

    def _extract_contour_segments(self, tricontour):
        """Extracts contour segments from matplotlib tricontour.

        Args:
            tricontour: Output from plt.tricontour.

        Returns:
            Segment dictionaries with 'x', 'y', and 'psi'.
        """
        segments = []
        for i, level in enumerate(tricontour.levels):
            for seg in tricontour.allsegs[i]:
                if len(seg) > 1:
                    segments.append({"x": seg[:, 0], "y": seg[:, 1], "psi": level})
        return segments

    @pn.depends("communicator.equilibrium", "show_separatrix")
    def _plot_separatrix(self):
        """Plots the separatrix from the equilibrium boundary.

        Returns:
            Holoviews curve containing the separatrix.
        """
        equilibrium = self.communicator.equilibrium
        if not self.show_separatrix or equilibrium is None:
            r = z = []
            contour = hv.Contours(([0], [0], 0), vdims="psi")
        else:
            r = equilibrium.time_slice[0].boundary.outline.r
            z = equilibrium.time_slice[0].boundary.outline.z

            boundary_psi = equilibrium.time_slice[0].boundary.psi
            contour = self._calc_contours(equilibrium, [boundary_psi])
        return hv.Curve((r, z)).opts(
            color="red",
            line_width=4,
            show_legend=False,
            hover_tooltips=[("", "Separatrix")],
        ) * contour.opts(self.CONTOUR_OPTS)

    @pn.depends("wall", "show_vacuum_vessel")
    def _plot_vacuum_vessel(self):
        """Generates path for inner and outer vacuum vessel.

        Returns:
            Holoviews path containing the geometry.
        """
        paths = []
        if self.show_vacuum_vessel and self.wall is not None:
            for unit in self.wall.description_2d[0].vessel.unit:
                name = str(unit.name)
                annular = unit.annular
                if len(annular.centreline.r):
                    paths.append((annular.centreline.r, annular.centreline.z, name))
                else:
                    paths.append(
                        (annular.outline_inner.r, annular.outline_inner.z, name)
                    )
                    paths.append(
                        (annular.outline_outer.r, annular.outline_outer.z, name)
                    )
        return _geometry_paths(paths)

    @pn.depends("wall", "show_wall")
    def _plot_wall(self):
        """Generates path for limiter and divertor.

        Returns:
            Holoviews path containing the geometry.
        """
        paths = []
        if self.show_wall and self.wall is not None:
            for unit in self.wall.description_2d[0].limiter.unit:
                name = str(unit.name)
                r_vals = unit.outline.r
                z_vals = unit.outline.z
                paths.append((r_vals, z_vals, name))
        return _geometry_paths(paths)

    @pn.depends("wall", "show_plasma_facing_components")
    def _plot_components(self):
        """Generates paths for the plasma facing components, which a machine
        describes alongside the limiter it is computed with.

        Returns:
            Holoviews path containing the geometry.
        """
        paths = []
        if self.show_plasma_facing_components and self.wall is not None:
            # The first description is the limiter the equilibrium is computed with
            for description in list(self.wall.description_2d)[1:]:
                for unit in description.limiter.unit:
                    outline = unit.outline
                    paths.append(
                        (outline.r, outline.z, str(unit.description or unit.name))
                    )
        return _geometry_paths(paths, color="gray", line_width=1)

    @pn.depends("pf_passive", "show_passive_structures")
    def _plot_passive_structures(self):
        """Generates paths for the passive conducting structures.

        Returns:
            Holoviews path containing the geometry.
        """
        paths = []
        if self.show_passive_structures and self.pf_passive is not None:
            paths = [
                (*_element_outline(element.geometry, loop.name), str(loop.name))
                for loop in self.pf_passive.loop
                for element in loop.element
            ]
        return _geometry_paths(paths, color="darkgray")

    @pn.depends("iron_core", "show_iron_core")
    def _plot_iron_core(self):
        """Generates paths for the iron core segments.

        Returns:
            Holoviews path containing the geometry.
        """
        paths = []
        if self.show_iron_core and self.iron_core is not None:
            paths = [
                (*_element_outline(segment.geometry, segment.name), str(segment.name))
                for segment in self.iron_core.segment
            ]
        return _geometry_paths(paths, color="saddlebrown")

    @pn.depends("communicator.equilibrium", "show_xo")
    def _plot_xo_points(self):
        """Plots X-points and O-points from the equilibrium.

        Returns:
            Scatter plots of X and O points.
        """
        o_points = []
        x_points = []
        equilibrium = self.communicator.equilibrium
        if self.show_xo and equilibrium is not None:
            for node in equilibrium.time_slice[0].contour_tree.node:
                point = (node.r, node.z)
                if node.critical_type == 1:
                    x_points.append(point)
                elif node.critical_type == 0 or node.critical_type == 2:
                    o_points.append(point)

        o_scatter = hv.Scatter(o_points).opts(
            marker="o",
            size=10,
            color="black",
            show_legend=False,
            hover_tooltips=[("", "O-point")],
        )
        x_scatter = hv.Scatter(x_points).opts(
            marker="x",
            size=10,
            color="black",
            show_legend=False,
            hover_tooltips=[("", "X-point")],
        )
        return o_scatter * x_scatter

    def __panel__(self):
        return self.panel_layout
