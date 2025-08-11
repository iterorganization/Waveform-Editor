import math

import holoviews as hv
import imas
import numpy as np
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.util import EquilibriumInput


class PlasmaShapeParams(param.Parameterized):
    """Helper class containing parameters to parameterize the plasma shape."""

    a = param.Number(default=1.9, step=0.01, bounds=[1, 2], label="Minor Radius")
    center_r = param.Number(
        default=6.2, step=0.01, bounds=[5, 7], label="Plasma center radius"
    )
    center_z = param.Number(
        default=0.545, step=0.01, bounds=[0, 1.5], label="Plasma center height"
    )
    kappa = param.Number(default=1.8, step=0.01, bounds=[0, 3], label="Elongation")
    delta = param.Number(default=0.43, step=0.01, bounds=[-1, 1], label="Triangularity")
    rx = param.Number(default=5.089, step=0.01, bounds=[4.5, 6], label="X-point radius")
    zx = param.Number(
        default=-3.346, step=0.01, bounds=[-4, -2], label="X-point height"
    )
    n_desired_bnd_points = param.Integer(
        default=96, bounds=[1, 200], label="Number of boundary points"
    )


class PlasmaShape(Viewer):
    PARAMETERIZED_INPUT = "Parameterized"
    EQUILIBRIUM_INPUT = "Equilibrium IDS"
    input_mode = param.ObjectSelector(
        default=EQUILIBRIUM_INPUT,
        objects=[EQUILIBRIUM_INPUT, PARAMETERIZED_INPUT],
        label="Shape input mode",
    )
    input = param.ClassSelector(class_=EquilibriumInput, default=EquilibriumInput())
    shape_params = param.ClassSelector(
        class_=PlasmaShapeParams, default=PlasmaShapeParams()
    )

    shape_curve = param.Parameter(
        default=hv.Curve([]), doc="Holoviews curve of the plasma shape"
    )
    has_shape = param.Boolean(doc="Whether a plasma shape is loaded.")

    def __init__(self):
        super().__init__()
        self.radio_box = pn.widgets.RadioBoxGroup.from_param(
            self.param.input_mode, inline=True, margin=(15, 20, 0, 20)
        )
        self.panel = pn.Column(self.radio_box, self._panel_shape_options)
        self.outline_r = None
        self.outline_z = None

    @pn.depends("shape_params.param", "input.param", "input_mode", watch=True)
    def _set_plasma_shape(self):
        """Update plasma boundary shape based on input mode."""

        outline_r = outline_z = None
        if self.input_mode == self.EQUILIBRIUM_INPUT:
            outline_r, outline_z = self._load_shape_from_ids()
        elif self.input_mode == self.PARAMETERIZED_INPUT:
            outline_r, outline_z = self._load_shape_from_params()

        if outline_r and outline_z:
            self.outline_r = outline_r
            self.outline_z = outline_z
            self.shape_curve = hv.Curve((outline_r, outline_z))
            self.has_shape = True
        else:
            self.outline_r = self.outline_z = np.empty(0)
            self.shape_curve = hv.Curve([])
            self.has_shape = False

    def _load_shape_from_ids(self):
        """Load plasma boundary outline from IDS equilibrium input.

        Returns:
            Tuple containing radial and vertical coordinates of the plasma boundary
                outline, or (None, None) if unavailable.
        """
        if not self.input.uri:
            return None, None
        try:
            with imas.DBEntry(self.input.uri, "r") as entry:
                equilibrium = entry.get_slice(
                    "equilibrium", self.input.time, imas.ids_defs.CLOSEST_INTERP
                )

            outline_r = equilibrium.time_slice[0].boundary.outline.r
            outline_z = equilibrium.time_slice[0].boundary.outline.z
            return outline_r, outline_z
        except Exception as e:
            pn.state.notifications.error(
                f"Could not load plasma boundary outline from {self.input.uri}:"
                f" {str(e)}"
            )
            return None, None

    def _load_shape_from_params(self):
        """Compute plasma boundary outline from parameterized shape inputs.

        Adapted from NICE, by Blaise Faugeras:
        https://gitlab.inria.fr/blfauger/nice

        Returns:
            Tuple containing radial and vertical coordinates of the plasma boundary
                outline
        """
        points = []
        nb_desired_point = self.shape_params.n_desired_bnd_points
        r0, z0 = self.shape_params.center_r, self.shape_params.center_z
        a = self.shape_params.a
        kappa = self.shape_params.kappa
        delta = self.shape_params.delta
        rx, zx = self.shape_params.rx, self.shape_params.zx

        # Calculate point distribution
        nb_point1 = (nb_desired_point - 1) // 2
        rem1 = (nb_desired_point - 1) % 2
        nb_point2 = (rem1 + nb_point1) // 2
        nb_point3 = nb_point2
        if (rem1 + nb_point1) % 2 == 1:
            nb_point1 += 1

        # First segment: main plasma shape
        theta1 = math.pi / (nb_point1 - 1)
        asin_delta = math.asin(delta)
        for i in range(nb_point1):
            theta = i * theta1
            r = r0 + a * math.cos(theta + asin_delta * math.sin(theta))
            z = z0 + a * kappa * math.sin(theta)
            points.append((r, z))

        # Second arc: inner divertor leg
        ri = ((rx + r0 - a) / 2.0) + ((z0 - zx) ** 2) / (2.0 * (rx - r0 + a))
        ai = ri - r0 + a
        theta2 = math.asin((z0 - zx) / ai) / (nb_point2 + 1)
        for i in range(nb_point2):
            theta = (i + 1) * theta2
            r = ri - ai * math.cos(theta)
            z = z0 - ai * math.sin(theta)
            points.append((r, z))

        # Third arc: outer divertor leg
        re = ((rx + r0 + a) / 2.0) + ((z0 - zx) ** 2) / (2.0 * (rx - r0 - a))
        ae = r0 + a - re
        theta3 = math.asin((z0 - zx) / ae) / (nb_point3 + 1)
        for i in range(nb_point3):
            theta = (i + 1) * theta3
            r = re + ae * math.cos(theta)
            z = z0 - ae * math.sin(theta)
            points.append((r, z))

        points.append((rx, zx))

        # Sort points by angle from centroid
        mean_r = sum(p[0] for p in points) / len(points)
        mean_z = sum(p[1] for p in points) / len(points)
        points.sort(key=lambda p: math.atan2(p[1] - mean_z, p[0] - mean_r))

        desired_bnd_r = [p[0] for p in points]
        desired_bnd_z = [p[1] for p in points]
        desired_bnd_r.append(desired_bnd_r[0])
        desired_bnd_z.append(desired_bnd_z[0])

        return desired_bnd_r, desired_bnd_z

    @param.depends("input_mode")
    def _panel_shape_options(self):
        if self.input_mode == self.PARAMETERIZED_INPUT:
            return pn.Param(self.shape_params, show_name=False)
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            return pn.Param(self.input, show_name=False)

    def __panel__(self):
        return self.panel
