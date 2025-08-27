import math
from dataclasses import dataclass

import imas
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.util import EquilibriumInput, WarningIndicator


class PlasmaShapeParams(param.Parameterized):
    """Helper class containing parameters to parameterize the plasma shape."""

    a = param.Number(default=1.9, step=0.01, softbounds=[1, 2], label="Minor Radius")
    center_r = param.Number(
        default=6.2, step=0.01, softbounds=[5, 7], label="Plasma center radius"
    )
    center_z = param.Number(
        default=0.545, step=0.01, softbounds=[0, 1.5], label="Plasma center height"
    )
    kappa = param.Number(default=1.8, step=0.01, softbounds=[0, 3], label="Elongation")
    delta = param.Number(
        default=0.43, step=0.01, softbounds=[-1, 1], label="Triangularity"
    )
    rx = param.Number(
        default=5.089, step=0.01, softbounds=[4.5, 6], label="X-point radius"
    )
    zx = param.Number(
        default=-3.346, step=0.01, softbounds=[-4, -2], label="X-point height"
    )
    n_desired_bnd_points = param.Integer(
        default=96, softbounds=[3, 200], label="Number of boundary points"
    )


class FormattedEditableFloatSlider(pn.widgets.EditableFloatSlider):
    def __init__(self, **params):
        super().__init__(format="1[.]000", **params)


@dataclass
class Gap:
    """Helper dataclass representing the properties of a gap."""

    name: str
    r: float  # Major radius of the reference point
    z: float  # Height of the reference point
    angle: float
    value: float

    @property
    def r_sep(self):
        """Major radius of the point on the desired separatrix"""
        return self.r + self.value * math.cos(-self.angle)

    @property
    def z_sep(self):
        """Height of the point on the desired separatrix"""
        return self.z + self.value * math.sin(-self.angle)


class PlasmaShape(Viewer):
    PARAMETERIZED_INPUT = "Parameterized"
    EQUILIBRIUM_INPUT = "Equilibrium IDS outline"
    GAP_INPUT = "Equilibrium IDS Gaps"
    input_mode = param.ObjectSelector(
        default=EQUILIBRIUM_INPUT,
        objects=[EQUILIBRIUM_INPUT, PARAMETERIZED_INPUT, GAP_INPUT],
        label="Shape input mode",
    )
    input_outline = param.ClassSelector(
        class_=EquilibriumInput, default=EquilibriumInput()
    )
    input_gaps = param.ClassSelector(
        class_=EquilibriumInput, default=EquilibriumInput()
    )
    shape_params = param.ClassSelector(
        class_=PlasmaShapeParams, default=PlasmaShapeParams()
    )

    has_shape = param.Boolean(doc="Whether a plasma shape is loaded.")
    shape_updated = param.Event(doc="Triggered whenever the plasma shape updates.")
    gap_ui = param.List(doc="List of UI elements containing the gap controls")

    def __init__(self):
        super().__init__()
        self.indicator = WarningIndicator(visible=self.param.has_shape.rx.not_())
        self.gap_grid = pn.Column(visible=self.param.gap_ui.rx.bool())
        self.radio_box = pn.widgets.RadioBoxGroup.from_param(
            self.param.input_mode, inline=True, margin=(15, 20, 0, 20)
        )
        self.panel = pn.Column(self.radio_box, self._panel_shape_options, self.gap_grid)
        self.outline_r = None
        self.outline_z = None
        self.gaps = []

    @param.depends("gap_ui", watch=True)
    def _update_gap_grid(self):
        """Update the gap grid when gap_ui changes."""
        self.gap_grid.clear()
        self.gap_grid.extend(self.gap_ui)

    @pn.depends(
        "shape_params.param",
        "input_outline.param",
        "input_gaps.param",
        "input_mode",
        watch=True,
    )
    def _set_plasma_shape(self):
        """Update plasma boundary shape based on input mode."""
        self.outline_r = self.outline_z = None
        self.gaps = []

        if self.input_mode == self.EQUILIBRIUM_INPUT:
            self._load_shape_from_ids()
        elif self.input_mode == self.PARAMETERIZED_INPUT:
            self._load_shape_from_params()
        elif self.input_mode == self.GAP_INPUT:
            self._load_shape_from_gaps()

        if self.outline_r and self.outline_z:
            self.has_shape = True
        else:
            self.has_shape = False
        self.param.trigger("shape_updated")

    def _load_shape_from_ids(self):
        """Load plasma boundary outline from IDS equilibrium input."""
        if not self.input_outline.uri:
            return
        try:
            with imas.DBEntry(self.input_outline.uri, "r") as entry:
                equilibrium = entry.get_slice(
                    "equilibrium", self.input_outline.time, imas.ids_defs.CLOSEST_INTERP
                )

            self.outline_r = equilibrium.time_slice[0].boundary.outline.r
            self.outline_z = equilibrium.time_slice[0].boundary.outline.z
        except Exception as e:
            pn.state.notifications.error(
                f"Could not load plasma boundary outline from {self.input_outline.uri}:"
                f" {str(e)}"
            )
            self.outline_r = self.outline_z = None

    def _load_shape_from_gaps(self):
        """Load plasma boundary outline from IDS equilibrium gap definitions."""
        self.gaps = []

        if self.input_gaps.uri:
            try:
                with imas.DBEntry(self.input_gaps.uri, "r") as entry:
                    equilibrium = entry.get_slice(
                        "equilibrium",
                        self.input_gaps.time,
                        imas.ids_defs.CLOSEST_INTERP,
                    )
                input_gaps = equilibrium.time_slice[0].boundary.gap
                if not input_gaps:
                    pn.state.notifications.error(
                        "The equilibrium IDS does not have any gaps"
                    )
                else:
                    for gap in input_gaps:
                        self.gaps.append(
                            Gap(
                                r=gap.r,
                                z=gap.z,
                                name=gap.name,
                                angle=gap.angle,
                                value=gap.value,
                            )
                        )
            except Exception as e:
                pn.state.notifications.error(
                    f"Could not load gaps from {self.input_gaps.uri}: {str(e)}"
                )

        self._update_outline_from_gaps()
        self._create_gap_ui()

    def _update_outline_from_gaps(self):
        """Update outline coordinates from current gap data."""
        if not self.gaps:
            self.outline_r = self.outline_z = None
            return

        self.outline_r = []
        self.outline_z = []
        for gap in self.gaps:
            self.outline_r.append(gap.r_sep)
            self.outline_z.append(gap.z_sep)

    def _on_gap_change(self, event):
        """Callback function triggered when gap UI values change."""
        self._sync_gaps_with_ui()
        self._update_outline_from_gaps()
        self.param.trigger("shape_updated")

    def _sync_gaps_with_ui(self):
        """Synchronize gap data with UI widget values."""
        for i, value_widget in enumerate(self.gap_ui):
            self.gaps[i].value = value_widget.value

    def _create_gap_ui(self):
        """Create the UI for each gap and populate the gap_ui list."""
        if not self.gaps:
            self.gap_ui = []
            return

        new_gap_ui = []
        for i, gap in enumerate(self.gaps):
            value_input = FormattedEditableFloatSlider(
                name=f"Gap {i}: {gap.name} Value [m]",
                value=float(gap.value),
                start=0,
                end=1,
                step=0.01,
                width=450,
            )
            value_input.param.watch(self._on_gap_change, "value")
            new_gap_ui.append(value_input)

        self.gap_ui = new_gap_ui

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

        self.outline_r = [p[0] for p in points]
        self.outline_z = [p[1] for p in points]

    @param.depends("input_mode")
    def _panel_shape_options(self):
        if self.input_mode == self.PARAMETERIZED_INPUT:
            params = pn.Param(self.shape_params, show_name=False)
            params.mapping[param.Number] = FormattedEditableFloatSlider
            params.mapping[param.Integer] = pn.widgets.EditableIntSlider
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            params = pn.Param(self.input_outline, show_name=False)
            params = pn.Row(params, self.indicator)
        elif self.input_mode == self.GAP_INPUT:
            params = pn.Param(self.input_gaps, show_name=False)
            params = pn.Row(params, self.indicator)
        return params

    def __panel__(self):
        return self.panel
