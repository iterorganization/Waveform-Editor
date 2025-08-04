import logging

import holoviews as hv
import matplotlib.pyplot as plt
import panel as pn
import param
from imas.ids_toplevel import IDSToplevel

from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.plotting_params import PlottingParams

logger = logging.getLogger(__name__)


class NicePlotter(param.Parameterized):
    communicator = param.ClassSelector(class_=NiceIntegration)
    wall = param.ClassSelector(class_=IDSToplevel)
    pf_active = param.ClassSelector(class_=IDSToplevel)
    plotting_params = param.ClassSelector(
        class_=PlottingParams, default=PlottingParams()
    )
    WIDTH = 800
    HEIGHT = 1000

    def __init__(self, communicator, **params):
        super().__init__(**params)
        self.communicator = communicator
        self.DEFAULT_OPTS = hv.opts.Overlay(
            xlim=(0, 13),
            ylim=(-10, 10),
            title="Equilibrium poloidal flux",
            xlabel="r [m]",
            ylabel="z [m]",
        )
        self.CONTOUR_OPTS = hv.opts.Contours(
            cmap="viridis",
            colorbar=True,
            tools=["hover"],
            colorbar_opts={"title": "Poloidal flux [Wb]"},
            show_legend=False,
        )

        self.plot_elements = {
            "contours": None,
            "separatrix": None,
            "xo_points": None,
            "coils": None,
            "wall": None,
            "vacuum_vessel": None,
        }

        # Adding as dependency doesn't trigger it, so manually add watcher
        self.plotting_params.param.watch(lambda event: self._plot_contours(), "levels")

    @pn.depends("plotting_params.param", "communicator.processing")
    def plot(self):
        """Generates the equilibrium plot with walls, PF coils, poloidal flux contours,
        separatrix, and critical points.

        Returns:
            PlotComposed Holoviews plot or loading pane.
        """
        overlay = hv.Overlay([])
        if self.plotting_params.show_contour and self.plot_elements["contours"]:
            overlay *= self.plot_elements["contours"]
        if self.plotting_params.show_separatrix and self.plot_elements["separatrix"]:
            overlay *= self.plot_elements["separatrix"]
        if self.plotting_params.show_xo and self.plot_elements["xo_points"]:
            overlay *= self.plot_elements["xo_points"]
        if (
            self.pf_active
            and self.plotting_params.show_coils
            and self.plot_elements["coils"]
        ):
            overlay *= self.plot_elements["coils"]
        if self.plotting_params.show_wall and self.plot_elements["wall"]:
            overlay *= self.plot_elements["wall"]
        if (
            self.plotting_params.show_vacuum_vessel
            and self.plot_elements["vacuum_vessel"]
        ):
            overlay *= self.plot_elements["vacuum_vessel"]

        # We cannot pass an empty overlay, so draw an empty curve in this case
        if not overlay.data:
            empty_placeholder = hv.Curve([]).opts(alpha=0)
            overlay = hv.Overlay([empty_placeholder])
        overlay = overlay.opts(self.DEFAULT_OPTS)
        pane = pn.pane.HoloViews(overlay, width=self.WIDTH, height=self.HEIGHT)

        # Show loading spinner if processing
        if self.communicator.processing:
            return pn.Column(pane, loading=True)
        return pane

    @pn.depends("pf_active", watch=True)
    def _plot_coil_rectangles(self):
        """Creates rectangular and path overlays for PF coils.

        Returns:
            Coil geometry overlay.
        """
        rectangles = []
        paths = []
        for coil in self.pf_active.coil:
            name = str(coil.name)
            for element in coil.element:
                rect = element.geometry.rectangle
                outline = element.geometry.outline
                if rect.has_value:
                    r0 = rect.r - rect.width / 2
                    r1 = rect.r + rect.width / 2
                    z0 = rect.z - rect.height / 2
                    z1 = rect.z + rect.height / 2
                    rectangles.append((r0, z0, r1, z1, name))
                elif outline.has_value:
                    paths.append((outline.r, outline.z, name))
                else:
                    logger.warning(
                        f"Coil {name} was skipped, as it does not have a filled 'rect' "
                        "or 'outline' node"
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

        self.plot_elements["coils"] = rects * paths

    @pn.depends("communicator.equilibrium", watch=True)
    def _plot_contours(self):
        """Generates contour plot for poloidal flux.

        Returns:
            Contour plot of psi.
        """
        equilibrium = self.communicator.equilibrium
        if not equilibrium:
            return
        eqggd = equilibrium.time_slice[0].ggd[0]
        r = eqggd.r[0].values
        z = eqggd.z[0].values
        psi = eqggd.psi[0].values

        trics = plt.tricontour(r, z, psi, levels=self.plotting_params.levels)
        self.plot_elements["contours"] = hv.Contours(
            self._extract_contour_segments(trics), vdims="psi"
        ).opts(self.CONTOUR_OPTS)

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

    @pn.depends("communicator.equilibrium", watch=True)
    def _plot_separatrix(self):
        """Plots the separatrix from the equilibrium boundary.

        Returns:
            Holoviews curve containing the separatrix.
        """
        equilibrium = self.communicator.equilibrium
        if not equilibrium:
            return
        r = equilibrium.time_slice[0].boundary.outline.r
        z = equilibrium.time_slice[0].boundary.outline.z
        separatrix = hv.Curve((r, z)).opts(
            color="red",
            line_width=2,
            show_legend=False,
            hover_tooltips=[("", "Separatrix")],
        )

        self.plot_elements["separatrix"] = separatrix

    @pn.depends("wall", watch=True)
    def _plot_vacuum_vessel(self):
        """Generates path overlays for inner and outer vacuum vessel.

        Returns:
            Holoviews overlay containing the geometry.
        """
        paths = []
        for unit in self.wall.description_2d[0].vessel.unit:
            name = str(unit.name)
            r_vals = unit.annular.centreline.r
            z_vals = unit.annular.centreline.z
            path = hv.Path([list(zip(r_vals, z_vals))], label=name).opts(
                color="black",
                line_width=2,
                hover_tooltips=[("", name)],
            )
            paths.append(path)
        self.plot_elements["vacuum_vessel"] = hv.Overlay(paths)

    @pn.depends("wall", watch=True)
    def _plot_wall(self):
        """Generates path overlays for limiter and divertor.

        Returns:
            Holoviews overlay containing the geometry.
        """
        paths = []
        for unit in self.wall.description_2d[0].limiter.unit:
            name = str(unit.name)
            r_vals = unit.outline.r
            z_vals = unit.outline.z
            path = hv.Path([list(zip(r_vals, z_vals))]).opts(
                color="black",
                line_width=2,
                hover_tooltips=[("", name)],
            )
            paths.append(path)
        self.plot_elements["wall"] = hv.Overlay(paths)

    @pn.depends("communicator.equilibrium", watch=True)
    def _plot_xo_points(self):
        """Plots X-points and O-points from the equilibrium.

        Returns:
            Scatter plots of X and O points.
        """
        equilibrium = self.communicator.equilibrium
        if not equilibrium:
            return
        o_points = []
        x_points = []
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
        self.plot_elements["xo_points"] = o_scatter * x_scatter
