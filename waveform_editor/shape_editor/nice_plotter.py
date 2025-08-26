import logging

import holoviews as hv
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import panel as pn
import param
from imas.ids_toplevel import IDSToplevel

from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.plasma_shape import PlasmaShape

matplotlib.use("Agg")
logger = logging.getLogger(__name__)


class NicePlotter(pn.viewable.Viewer):
    # Input data, use negative precedence to hide from the UI
    communicator = param.ClassSelector(class_=NiceIntegration, precedence=-1)
    wall = param.ClassSelector(class_=IDSToplevel, precedence=-1)
    pf_active = param.ClassSelector(class_=IDSToplevel, precedence=-1)
    plasma_shape = param.ClassSelector(class_=PlasmaShape, precedence=-1)

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

    WIDTH = 800
    HEIGHT = 1000

    def __init__(self, communicator, plasma_shape, **params):
        super().__init__(**params, communicator=communicator, plasma_shape=plasma_shape)
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
        self.DESIRED_SHAPE_OPTS = hv.opts.Curve(color="blue")

        plot_elements = [
            hv.DynamicMap(self._plot_contours),
            hv.DynamicMap(self._plot_separatrix),
            hv.DynamicMap(self._plot_xo_points),
            hv.DynamicMap(self._plot_coil_rectangles),
            hv.DynamicMap(self._plot_wall),
            hv.DynamicMap(self._plot_vacuum_vessel),
            hv.DynamicMap(self._plot_desired_shape),
        ]
        overlay = hv.Overlay(plot_elements).collate().opts(self.DEFAULT_OPTS)
        self.panel = pn.Column(
            pn.pane.HoloViews(overlay, width=self.WIDTH, height=self.HEIGHT),
            loading=self.communicator.param.processing,
        )

    @pn.depends("plasma_shape.shape_updated", "show_desired_shape")
    def _plot_desired_shape(self):
        if not self.show_desired_shape or not self.plasma_shape.has_shape:
            return hv.Overlay([hv.Curve([]).opts(self.DESIRED_SHAPE_OPTS)])

        r = self.plasma_shape.outline_r
        z = self.plasma_shape.outline_z

        # Ensure the desired shape is closed
        if r[0] != r[-1] or z[0] != z[-1]:
            r = np.append(r, r[0])
            z = np.append(z, z[0])
        plot_elements = [hv.Curve((r, z)).opts(self.DESIRED_SHAPE_OPTS)]

        if self.plasma_shape.input_mode == self.plasma_shape.GAP_INPUT:
            for gap in self.plasma_shape.gaps:
                plot_elements.append(
                    hv.Scatter(([gap.r], [gap.z])).opts(color="red", size=6)
                )
                plot_elements.append(
                    hv.Segments([(gap.r, gap.z, gap.r_sep, gap.z_sep)]).opts(
                        color="black"
                    )
                )
        return hv.Overlay(plot_elements)

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
                if self.communicator.pf_active:
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
            return hv.Contours(([0], [0], 0), vdims="psi").opts(self.CONTOUR_OPTS)

        return self._calc_contours(equilibrium, self.levels).opts(self.CONTOUR_OPTS)

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
        return self.panel
