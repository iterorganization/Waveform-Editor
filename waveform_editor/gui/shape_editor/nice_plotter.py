import logging

import holoviews as hv
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import panel as pn
import param
from bokeh.models import HoverTool
from imas.ids_toplevel import IDSToplevel
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.plasma_properties import PlasmaProperties
from waveform_editor.gui.shape_editor.plasma_shape import PlasmaShape
from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration

matplotlib.use("Agg")
logger = logging.getLogger(__name__)


def _as_weight(value):
    """A point's weight as a whole number of repeats, at least 1."""
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 1


def _no_hover(element):
    """Exclude an element's renderer from every HoverTool in the shared figure."""

    def hook(plot, _):
        renderer = plot.handles.get("glyph_renderer")
        for tool in plot.state.toolbar.tools:
            if isinstance(tool, HoverTool) and renderer in (tool.renderers or []):
                tool.renderers = [r for r in tool.renderers if r is not renderer]

    return element.opts(hooks=[hook])


class NicePlotter(Viewer):
    # Input data, use negative precedence to hide from the UI
    communicator = param.ClassSelector(class_=NiceIntegration, precedence=-1)
    wall = param.ClassSelector(class_=IDSToplevel, precedence=-1)
    pf_active = param.ClassSelector(class_=IDSToplevel, precedence=-1)
    plasma_shape = param.ClassSelector(class_=PlasmaShape, precedence=-1)
    plasma_properties = param.ClassSelector(class_=PlasmaProperties, precedence=-1)
    nice_settings = param.ClassSelector(class_=NiceSettings, precedence=-1)

    # Plot parameters
    show_contour = param.Boolean(default=True, label="Show contour lines")
    levels = param.Integer(
        default=20, bounds=(1, 200), label="Number of contour levels"
    )
    show_coils = param.Boolean(default=True, label="Show coils")
    show_wall = param.Boolean(default=True, label="Show limiter and divertor")
    show_vacuum_vessel = param.Boolean(
        default=True, label="Show inner and outer vacuum vessel"
    )
    show_xo = param.Boolean(default=True, label="Show x-point and o-point")
    show_separatrix = param.Boolean(default=True, label="Show separatrix")
    show_desired_shape = param.Boolean(default=True, label="Show desired shape")

    # Renderer of the editable points, set once the plot is first rendered
    _points_renderer = None
    _pushing_points = False
    _applying_draw = False

    # Bokeh cannot hold a data aspect while it resizes, so fix the size instead
    R_RANGE = (0, 13)
    Z_RANGE = (-10, 10)
    FRAME_HEIGHT = 700
    FRAME_WIDTH = round(
        FRAME_HEIGHT * (R_RANGE[1] - R_RANGE[0]) / (Z_RANGE[1] - Z_RANGE[0])
    )

    def __init__(self, **params):
        super().__init__(**params)
        self.DEFAULT_OPTS = hv.opts.Overlay(
            xlim=self.R_RANGE,
            ylim=self.Z_RANGE,
            frame_width=self.FRAME_WIDTH,
            frame_height=self.FRAME_HEIGHT,
            title="",
            xlabel="r [m]",
            ylabel="z [m]",
            fontsize={"labels": 15, "ticks": 11},
        )
        self.nice_settings = settings.nice
        self._shape_plotters = {
            self.plasma_shape.GAP_INPUT: self._plot_gaps,
        }
        self.CONTOUR_OPTS = hv.opts.Contours(
            cmap="viridis",
            colorbar=True,
            tools=["hover"],
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
            hv.DynamicMap(self._plot_contours),
            hv.DynamicMap(self._plot_separatrix),
            hv.DynamicMap(self._plot_xo_points),
            hv.DynamicMap(self._plot_coil_rectangles),
            hv.DynamicMap(self._plot_wall),
            hv.DynamicMap(self._plot_vacuum_vessel),
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
        shape = self.plasma_shape
        if self.nice_settings.is_direct_mode:
            return False
        return shape.input_mode == shape.WEIGHTED_POINTS_INPUT or (
            shape.input_mode == shape.PARAMETERIZED_INPUT
            and shape.shape_params.extra_points_enabled
        )

    def _capture_points_renderer(self, plot, element):
        """Keep hold of the renderer, so the points can be hidden without redrawing
        them, which would break the draw tool."""
        self._points_renderer = plot.handles.get("glyph_renderer")
        self._update_points_visibility()

    def _update_points_visibility(self, *events):
        """Only show the points while they are in use."""
        if self._points_renderer is not None:
            self._points_renderer.visible = self._uses_weighted_points()

    def _push_points_to_plot(self, *events):
        """Mirror the table onto the plot, for rows edited or deleted in the table.

        The points are written straight into the renderer rather than redrawn,
        because redrawing them would break the draw tool.
        """
        # The plot already shows the points it just handed us
        if self._points_renderer is None or self._applying_draw:
            return
        table = self.plasma_shape.weighted_points_table
        r, z = table.get_points()
        data = {
            "r": list(r or []),
            "z": list(z or []),
            "weight": table.get_weights(),
        }

        def apply():
            self._pushing_points = True
            try:
                self._points_renderer.data_source.data = data
            finally:
                self._pushing_points = False

        # Scheduled, so that the document lock is held while the model is changed
        pn.state.execute(apply)

    def _on_point_draw(self, data):
        """Write points added, dragged or deleted on the plot back to the table."""
        if not data or self._pushing_points or not self._uses_weighted_points():
            return
        r, z = data.get("r", []), data.get("z", [])
        # A point added on the plot arrives without a weight, and a weight below 1
        # would drop it from the boundary
        weights = [_as_weight(w) for w in data.get("weight", [])]
        weights += [1] * (len(r) - len(weights))
        self._applying_draw = True
        try:
            self.plasma_shape.weighted_points_table.set_points(r, z, weights)
        finally:
            self._applying_draw = False

    @pn.depends(
        "plasma_shape.shape_updated", "show_desired_shape", "nice_settings.mode"
    )
    def _plot_plasma_shape(self):
        if (
            self.nice_settings.is_direct_mode
            or not self.show_desired_shape
            or not self.plasma_shape.has_shape
        ):
            return hv.Overlay([hv.Curve([]).opts(self.DESIRED_SHAPE_OPTS)])

        # The weighted points are drawn by the editable points element instead
        if self.plasma_shape.input_mode == self.plasma_shape.WEIGHTED_POINTS_INPUT:
            return hv.Overlay([hv.Curve([]).opts(self.DESIRED_SHAPE_OPTS)])

        if self.plasma_shape.input_mode == self.plasma_shape.PARAMETERIZED_INPUT:
            if self.plasma_shape.param_weights:
                return self._plot_weighted_boundary()
            # The parameterized points, so that extra points appended to the outline
            # are not drawn as part of the boundary curve
            return self._plot_outline_shape(
                self.plasma_shape.param_r, self.plasma_shape.param_z
            )

        r = self.plasma_shape.outline_r
        z = self.plasma_shape.outline_z
        plotter = self._shape_plotters.get(
            self.plasma_shape.input_mode, self._plot_outline_shape
        )
        return plotter(r, z)

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
        paths = hv.Path(paths, vdims=["name"]).opts(
            color="black",
            line_width=1,
            show_legend=False,
            hover_tooltips=[("", "@name")],
        )
        return rects * paths

    @pn.depends("communicator.equilibrium", "show_contour", "levels")
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

        return contours.opts(self.CONTOUR_OPTS)

    def _calc_contours(self, equilibrium, levels):
        """Calculates the contours of the psi grid of an equilibrium IDS.

        Args:
            equilibrium: The equilibrium IDS to load psi grid from.
            levels: Determines the number of contour lines. Either an integer for total
                number of contour lines, or a list of specified levels.

        Returns:
            Holoviews contours object
        """

        eqggd = equilibrium.time_slice[0].ggd[0]
        r = eqggd.r[0].values
        z = eqggd.z[0].values
        psi = eqggd.psi[0].values

        if not r or not z or not psi:
            pn.state.notifications.error(
                "NICE did not produce a valid poloidal flux field"
            )
            return hv.Contours(([0], [0], 0), vdims="psi")

        trics = plt.tricontour(r, z, psi, levels=levels)
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
                r_vals = unit.annular.centreline.r
                z_vals = unit.annular.centreline.z
                paths.append((r_vals, z_vals, name))
        return hv.Path(paths, vdims=["name"]).opts(
            color="black",
            line_width=2,
            hover_tooltips=[("", "@name")],
        )

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
        return hv.Path(paths, vdims=["name"]).opts(
            color="black",
            line_width=2,
            hover_tooltips=[("", "@name")],
        )

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
