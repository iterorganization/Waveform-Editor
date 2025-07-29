import holoviews as hv
import matplotlib.pyplot as plt
import panel as pn
import param

from waveform_editor.shape_editor.nice_integration import NiceIntegration


class NicePlotter(param.Parameterized):
    levels = param.Integer(default=20, bounds=(1, 200))
    communicator = param.ClassSelector(class_=NiceIntegration)

    def __init__(self, communicator, wall, **params):
        super().__init__(**params)
        self.communicator = communicator
        self.wall = wall

    @pn.depends("levels", "communicator.processing")
    def plot(self, width=1000, height=1000):
        if self.communicator.processing:
            return pn.indicators.LoadingSpinner(value=True, size=40, name="Loading...")
        elif not self.communicator.processing and self.communicator.equilibrium:
            contours = self._create_contours(self.communicator.equilibrium, self.levels)
            coils = self._create_coil_rectangles(self.communicator.pf_active)
            wall_plot = self._create_wall(self.wall)
            separatrix = self._create_separatrix(self.communicator.equilibrium)
            points = self._create_xo_points(self.communicator.equilibrium)
            overlay = contours * coils * separatrix * points * wall_plot
            overlay = overlay.opts(ylim=(-10, 10))
            return pn.pane.HoloViews(overlay, width=width, height=height)
        else:
            return None

    def _extract_contour_segments(self, tricontour):
        segments = []
        for i, level in enumerate(tricontour.levels):
            for seg in tricontour.allsegs[i]:
                if len(seg) > 1:
                    segments.append({"x": seg[:, 0], "y": seg[:, 1], "psi": level})
        return segments

    def _create_coil_rectangles(self, pf_active):
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

    def _create_contours(self, equilibrium, levels):
        eqggd = equilibrium.time_slice[0].ggd[0]
        r = eqggd.r[0].values
        z = eqggd.z[0].values
        psi = eqggd.psi[0].values
        time = self.communicator.equilibrium.time[
            0
        ]  # time may not be filled for homogeneous
        time_meta = self.communicator.equilibrium.time.metadata
        r_meta = eqggd.r.metadata
        z_meta = eqggd.z.metadata
        psi_meta = eqggd.psi.metadata

        trics = plt.tricontour(r, z, psi, levels=levels)
        contours = hv.Contours(self._extract_contour_segments(trics), vdims="psi").opts(
            cmap="viridis",
            colorbar=True,
            tools=["hover"],
            title=f"equilibrium poloidal flux at time: {time:.2f} {time_meta.units}",
            xlabel=f"{r_meta.name} [{r_meta.units}]",
            ylabel=f"{z_meta.name} [{z_meta.units}]",
            colorbar_opts={"title": f"{psi_meta.name} [{psi_meta.units}]"},
            show_legend=False,
        )
        return contours

    def _create_separatrix(self, equilibrium):
        r = equilibrium.time_slice[0].boundary.outline.r
        z = equilibrium.time_slice[0].boundary.outline.z
        separatrix = hv.Curve((r, z)).opts(color="red", line_width=2, show_legend=False)
        return separatrix

    def _create_wall(self, wall):
        centreline = wall.description_2d[0].vessel.unit[0].annular.centreline
        r = centreline.r
        z = centreline.z
        path = hv.Path([(r, z)]).opts(color="black", line_width=2)
        return path

    def _create_xo_points(self, equilibrium):
        o_points = [
            (node.r, node.z)
            for node in equilibrium.time_slice[0].contour_tree.node
            if node.critical_type == 0 or node.critical_type == 2
        ]
        x_points = [
            (node.r, node.z)
            for node in equilibrium.time_slice[0].contour_tree.node
            if node.critical_type == 1
        ]
        o_scatter = hv.Scatter(o_points).opts(
            marker="o", size=10, color="black", show_legend=False
        )
        x_scatter = hv.Scatter(x_points).opts(
            marker="x", size=10, color="black", show_legend=False
        )
        return o_scatter * x_scatter
