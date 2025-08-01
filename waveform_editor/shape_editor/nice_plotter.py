import logging

import holoviews as hv
import matplotlib.pyplot as plt
import panel as pn
import param

from waveform_editor.shape_editor.nice_integration import NiceIntegration

logger = logging.getLogger(__name__)


class NicePlotter(param.Parameterized):
    communicator = param.ClassSelector(class_=NiceIntegration)

    DEFAULT_OPTS = {
        "xlim": (0, 13),
        "ylim": (-10, 10),
        "title": "Equilibrium poloidal flux",
        "xlabel": "r [m]",
        "ylabel": "z [m]",
    }
    COLORBAR_OPTS = {"title": "Poloidal flux [Wb]"}
    WIDTH = 800
    HEIGHT = 1000

    def __init__(self, communicator, plotting_params, **params):
        super().__init__(**params)
        self.communicator = communicator
        self.plotting_params = plotting_params
        self.wall = None
        self.pf_active = None

    @pn.depends("plotting_params.param", "communicator.processing")
    def plot(self):
        """Generates the equilibrium plot with walls, PF coils, poloidal flux contours,
        separatrix, and critical points.

        Returns:
            PlotComposed Holoviews plot or loading pane.
        """
        equilibrium = self.communicator.equilibrium

        overlay = hv.Overlay([])
        if equilibrium:
            if self.plotting_params.show_contour:
                overlay *= self._plot_contours(equilibrium, self.plotting_params.levels)
            if self.plotting_params.show_separatrix:
                overlay *= self._plot_separatrix(equilibrium)
            if self.plotting_params.show_xo:
                overlay *= self._plot_xo_points(equilibrium)
        if self.pf_active and self.plotting_params.show_coils:
            overlay *= self._plot_coil_rectangles(self.pf_active)
        if self.wall:
            if self.plotting_params.show_wall:
                overlay *= self._plot_wall(self.wall)
            if self.plotting_params.show_vacuum_vessel:
                overlay *= self._plot_vacuum_vessel(self.wall)

        # We cannot pass an empty overlay, so draw an empty curve in this case
        if not overlay.data:
            empty_placeholder = hv.Curve([]).opts(alpha=0)
            overlay = hv.Overlay([empty_placeholder])
        overlay = overlay.opts(**self.DEFAULT_OPTS)
        pane = pn.pane.HoloViews(overlay, width=self.WIDTH, height=self.HEIGHT)

        # Show loading spinner if processing
        if self.communicator.processing:
            return pn.Column(pane, loading=True)
        return pane

    def _plot_coil_rectangles(self, pf_active):
        """Creates rectangular and path overlays for PF coils.

        Args:
            pf_active: Poloidal field coil data.

        Returns:
            Coil geometry overlay.
        """
        rectangles = []
        paths = []
        for coil in pf_active.coil:
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

        return rects * paths

    def _plot_contours(self, equilibrium, levels):
        """Generates contour plot for poloidal flux.

        Args:
            equilibrium: an equilibrium IDS.
            levels: Number of contour levels.

        Returns:
            Contour plot of psi.
        """
        eqggd = equilibrium.time_slice[0].ggd[0]
        r = eqggd.r[0].values
        z = eqggd.z[0].values
        psi = eqggd.psi[0].values

        trics = plt.tricontour(r, z, psi, levels=levels)
        contours = hv.Contours(self._extract_contour_segments(trics), vdims="psi").opts(
            cmap="viridis",
            colorbar=True,
            tools=["hover"],
            colorbar_opts=self.COLORBAR_OPTS,
            show_legend=False,
        )
        return contours

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

    def _plot_separatrix(self, equilibrium):
        """Plots the separatrix from the equilibrium boundary.

        Args:
            equilibrium: an equilibrium IDS.

        Returns:
            Holoviews curve containing the separatrix.
        """
        r = equilibrium.time_slice[0].boundary.outline.r
        z = equilibrium.time_slice[0].boundary.outline.z
        separatrix = hv.Curve((r, z)).opts(
            color="red",
            line_width=2,
            show_legend=False,
            hover_tooltips=[("", "Separatrix")],
        )

        return separatrix

    def _plot_vacuum_vessel(self, wall):
        """Generates path overlays for inner and outer vacuum vessel.

        Args:
            wall: a wall IDS.

        Returns:
            Holoviews overlay containing the geometry.
        """
        paths = []
        for unit in wall.description_2d[0].vessel.unit:
            name = str(unit.name)
            r_vals = unit.annular.centreline.r
            z_vals = unit.annular.centreline.z
            path = hv.Path([list(zip(r_vals, z_vals))], label=name).opts(
                color="black",
                line_width=2,
                hover_tooltips=[("", name)],
            )
            paths.append(path)
        return hv.Overlay(paths)

    def _plot_wall(self, wall):
        """Generates path overlays for limiter and divertor.

        Args:
            wall: a wall IDS.

        Returns:
            Holoviews overlay containing the geometry.
        """
        paths = []
        for unit in wall.description_2d[0].limiter.unit:
            name = str(unit.name)
            r_vals = unit.outline.r
            z_vals = unit.outline.z
            path = hv.Path([list(zip(r_vals, z_vals))]).opts(
                color="black",
                line_width=2,
                hover_tooltips=[("", name)],
            )
            paths.append(path)
        return hv.Overlay(paths)

    def _plot_xo_points(self, equilibrium):
        """Plots X-points and O-points from the equilibrium.

        Args:
            equilibrium: an equilibrium IDS.

        Returns:
            Scatter plots of X and O points.
        """
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
        return o_scatter * x_scatter
