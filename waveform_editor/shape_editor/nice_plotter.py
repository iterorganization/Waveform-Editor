import holoviews as hv
import matplotlib.pyplot as plt
import panel as pn
import param

from waveform_editor.shape_editor.nice_integration import NiceIntegration


class NicePlotter(param.Parameterized):
    levels = param.Integer(default=20, bounds=(1, 200))
    communicator = param.ClassSelector(class_=NiceIntegration)

    DEFAULT_OPTS = {
        "xlim": (0, 13),
        "ylim": (-10, 10),
        "title": "Equilibrium poloidal flux",
        "xlabel": "r [m]",
        "ylabel": "z [m]",
    }
    COLORBAR_OPTS = {"title": "ψ [Wb]"}
    WIDTH = 800
    HEIGHT = 1000

    def __init__(self, communicator, wall, pf_active, **params):
        super().__init__(**params)
        self.communicator = communicator
        coils = self._plot_coil_rectangles(pf_active)
        wall_plot = self._plot_wall(wall)
        default_overlay = coils * wall_plot

        # Create dummy data so a colorbar can be shown for the default plot
        dummy_data = hv.Contours([{"x": [0], "y": [0], "psi": 0}], vdims="psi").opts(
            cmap="viridis",
            colorbar=True,
            colorbar_opts=self.COLORBAR_OPTS,
            show_legend=False,
            alpha=0,
        )
        self.default_overlay = (default_overlay * dummy_data).opts(**self.DEFAULT_OPTS)
        self.default_pane = pn.pane.HoloViews(
            self.default_overlay,
            width=self.WIDTH,
            height=self.HEIGHT,
        )

    @pn.depends("levels", "communicator.processing")
    def plot(self):
        """Generates the equilibrium plot with walls, PF coils, contours,
        separatrix, and critical points.

        Returns:
            Composed Holoviews plot or loading pane.
        """
        if not self.communicator.processing and self.communicator.equilibrium:
            contours = self._plot_contours(self.communicator.equilibrium, self.levels)
            separatrix = self._plot_separatrix(self.communicator.equilibrium)
            points = self._plot_xo_points(self.communicator.equilibrium)
            overlay = self.default_overlay * separatrix * points * contours
            overlay = overlay.opts(**self.DEFAULT_OPTS)
            return pn.pane.HoloViews(
                overlay,
                width=self.WIDTH,
                height=self.HEIGHT,
            )
        elif self.communicator.processing:
            return pn.Column(self.default_pane, loading=True)
        else:
            return self.default_pane

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
            for element in coil.element:
                rect = element.geometry.rectangle
                outline = element.geometry.outline
                if rect.has_value:
                    r0 = rect.r - rect.width / 2
                    r1 = rect.r + rect.width / 2
                    z0 = rect.z - rect.height / 2
                    z1 = rect.z + rect.height / 2
                    rectangles.append((r0, z0, r1, z1))
                elif outline.has_value:
                    path = hv.Path([list(zip(outline.r, outline.z))]).opts(
                        color="black", line_width=1, show_legend=False
                    )
                    paths.append(path)
                else:
                    continue
        rects = hv.Rectangles(rectangles).opts(
            line_color="black", fill_alpha=0, line_width=2, show_legend=False
        )

        return rects * hv.Overlay(paths)

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
        separatrix = hv.Curve((r, z)).opts(color="red", line_width=2, show_legend=False)
        return separatrix

    def _plot_wall(self, wall):
        """Generates path overlays for vacuum vessel, limiter, and divertor.

        Args:
            wall: a wall IDS.

        Returns:
            Holoviews overlay containing the wall geometry.
        """
        paths = []

        # Vacuum vessel
        for unit in wall.description_2d[0].vessel.unit:
            r_vals = unit.annular.centreline.r
            z_vals = unit.annular.centreline.z
            path = hv.Path([list(zip(r_vals, z_vals))]).opts(
                color="black", line_width=2
            )
            paths.append(path)

        # Limiter and Divertor
        for unit in wall.description_2d[0].limiter.unit:
            r_vals = unit.outline.r
            z_vals = unit.outline.z
            path = hv.Path([list(zip(r_vals, z_vals))]).opts(
                color="black", line_width=2
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
            marker="o", size=10, color="black", show_legend=False
        )
        x_scatter = hv.Scatter(x_points).opts(
            marker="x", size=10, color="black", show_legend=False
        )
        return o_scatter * x_scatter
