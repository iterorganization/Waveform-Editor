import math

import holoviews as hv
import imas
import numpy as np
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.util import load_slice


class ShapeParams(Viewer):
    """Parameters related to plasma shape"""

    PARAMETERIZED_INPUT = "Parameterized"
    EQUILIBRIUM_INPUT = "Equilibrium IDS"
    input_mode = param.ObjectSelector(
        default=EQUILIBRIUM_INPUT,
        objects=[EQUILIBRIUM_INPUT, PARAMETERIZED_INPUT],
        label="Shape input mode",
    )

    shape_curve = param.Parameter(
        default=hv.Curve([]), doc="Holoviews curve of the plasma shape"
    )
    has_shape = param.Boolean(doc="Whether a plasma shape is loaded.")

    equilibrium_input = param.String(label="Input 'equilibrium' IDS")
    time_input = param.Number(label="Time for input equilibrium")

    a = param.Number(default=1.9, bounds=[1, 2], label="a")
    center_r = param.Number(default=6.2, bounds=[5, 7], label="center_r")
    center_z = param.Number(default=0.545, bounds=[0, 1.5], label="center_z")
    kappa = param.Number(default=1.8, bounds=[0, 3], label="kappa")
    delta = param.Number(default=0.43, bounds=[-1, 1], label="delta")
    rx = param.Number(default=5.089, bounds=[4.5, 6], label="rx")
    zx = param.Number(default=-3.346, bounds=[-4, -2], label="zx")
    n_desired_bnd_points = param.Integer(
        default=96, bounds=[1, 200], label="n_desired_bnd_points"
    )

    def __init__(self, equilibrium):
        super().__init__()
        self.equilibrium = equilibrium
        for p in self.param:
            if p != "shape_curve" and p != "has_shape":
                self.param.watch(self._set_plasma_shape, p)

    def _set_plasma_shape(self, event):
        outline_r = outline_z = None
        if self.input_mode == self.EQUILIBRIUM_INPUT:
            outline_r, outline_z = self._load_shape_from_ids()
        elif self.input_mode == self.PARAMETERIZED_INPUT:
            outline_r, outline_z = self._load_shape_from_params()

        if outline_r and outline_z:
            self.equilibrium.time_slice[0].boundary.outline.r = outline_r
            self.equilibrium.time_slice[0].boundary.outline.z = outline_z
            self.shape_curve = hv.Curve((outline_r, outline_z))
            self.has_shape = True
        else:
            self.equilibrium.time_slice[0].boundary.outline.r.value = np.empty(0)
            self.equilibrium.time_slice[0].boundary.outline.z.value = np.empty(0)
            self.shape_curve = hv.Curve([])
            self.has_shape = False

    def _load_shape_from_ids(self):
        try:
            with imas.DBEntry(self.equilibrium_input, "r") as entry:
                equilibrium = entry.get_slice(
                    "equilibrium", self.time_input, imas.ids_defs.CLOSEST_INTERP
                )

            outline_r = equilibrium.time_slice[0].boundary.outline.r
            outline_z = equilibrium.time_slice[0].boundary.outline.z
            return outline_r, outline_z
        except Exception as e:
            pn.state.notifications.error(
                f"Could not load plasma boundary outline from {self.equilibrium_input}:"
                f" {str(e)}"
            )
            return None, None

    def _load_shape_from_params(self):
        desired_r = []
        desired_z = []

        nb_desired_point = self.n_desired_bnd_points
        r0 = self.center_r
        z0 = self.center_z
        a = self.a
        kappa = self.kappa
        delta = self.delta
        rx = self.rx
        zx = self.zx

        nb_point1 = (nb_desired_point - 1) // 2
        rem1 = (nb_desired_point - 1) % 2
        nb_point2 = (rem1 + nb_point1) // 2
        nb_point3 = nb_point2
        if (rem1 + nb_point1) % 2 == 1:
            nb_point1 += 1

        theta1 = math.pi / (nb_point1 - 1)
        for i in range(nb_point1):
            theta = i * theta1
            desired_r.append(
                r0 + a * math.cos(theta + math.asin(delta) * math.sin(theta))
            )
            desired_z.append(z0 + a * kappa * math.sin(theta))

        ri = ((rx + r0 - a) / 2.0) + ((z0 - zx) ** 2) / (2.0 * (rx - r0 + a))
        ai = ri - r0 + a
        theta2 = math.asin((z0 - zx) / ai) / (nb_point2 + 1)
        for i in range(nb_point2):
            theta = (i + 1) * theta2
            desired_r.append(ri - ai * math.cos(theta))
            desired_z.append(z0 - ai * math.sin(theta))

        re = ((rx + r0 + a) / 2.0) + ((z0 - zx) ** 2) / (2.0 * (rx - r0 - a))
        ae = r0 + a - re
        theta3 = math.asin((z0 - zx) / ae) / (nb_point3 + 1)
        for i in range(nb_point3):
            theta = (i + 1) * theta3
            desired_r.append(re + ae * math.cos(theta))
            desired_z.append(z0 - ae * math.sin(theta))

        desired_r.append(rx)
        desired_z.append(zx)

        points = list(zip(desired_r, desired_z))
        mean_r = sum(desired_r) / len(desired_r)
        mean_z = sum(desired_z) / len(desired_z)

        def angle_from_mean(p):
            return math.atan2(p[1] - mean_z, p[0] - mean_r)

        p_sorted = sorted(points, key=angle_from_mean)
        desired_bnd_r = [p[0] for p in p_sorted]
        desired_bnd_z = [p[1] for p in p_sorted]
        desired_bnd_r.append(desired_bnd_r[0])
        desired_bnd_z.append(desired_bnd_z[0])

        return desired_bnd_r, desired_bnd_z

    @param.depends("input_mode")
    def _dynamic_panel(self):
        widgets = {
            "input_mode": {"widget_type": pn.widgets.RadioBoxGroup, "inline": True}
        }
        if self.input_mode == self.PARAMETERIZED_INPUT:
            parameters = pn.Param(
                self,
                parameters=[
                    "input_mode",
                    "a",
                    "center_r",
                    "center_z",
                    "kappa",
                    "delta",
                    "rx",
                    "zx",
                    "n_desired_bnd_points",
                ],
                widgets=widgets,
                show_name=False,
            )
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            parameters = pn.Param(
                self,
                parameters=[
                    "input_mode",
                    "equilibrium_input",
                    "time_input",
                ],
                widgets=widgets,
                show_name=False,
            )

        return parameters

    def __panel__(self):
        return pn.Column(self._dynamic_panel)
