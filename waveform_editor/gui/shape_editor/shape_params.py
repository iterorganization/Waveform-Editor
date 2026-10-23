import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.util import (
    INPUT_WIDTH,
    FixedWidthEditableIntSlider,
    FormattedEditableFloatSlider,
)
from waveform_editor.settings import NiceSettings, settings

# A shape to start from for each machine, taken from one of its discharges, as
# (value, slider range) per parameter
MACHINE_SHAPES = {
    NiceSettings.PRESET_ITER: {
        "a": (1.98, (1, 2.5)),
        "center_r": (6.21, (5, 7)),
        "center_z": (0.87, (0, 1.5)),
        "kappa": (1.58, (0, 3)),
        "delta": (0.41, (-1, 1)),
        "rx": (5.117, (4.5, 6)),
        "zx": (-3.414, (-4, -2)),
        "rx_upper": (5.089, (4.5, 6)),
        "zx_upper": (3.346, (2, 4)),
    },
    NiceSettings.PRESET_WEST: {
        "a": (0.46, (0.2, 0.8)),
        "center_r": (2.54, (2, 3)),
        "center_z": (-0.02, (-0.5, 0.5)),
        "kappa": (1.31, (0, 3)),
        "delta": (0.38, (-1, 1)),
        "rx": (2.23, (1.8, 3.2)),
        "zx": (-0.62, (-1.2, 0)),
        "rx_upper": (2.23, (1.8, 3.2)),
        "zx_upper": (0.62, (0, 1.2)),
    },
}


def _group(title, *children, visible=True):
    """A group of inputs under a divider and a title, without a box around it."""
    return pn.Column(
        pn.pane.HTML(
            f"<hr style='margin:4px 0 8px 0;border-color:#dee2e6;'><b>{title}</b>",
            sizing_mode="stretch_width",
            margin=0,
        ),
        pn.FlexBox(*children, margin=0),
        sizing_mode="stretch_width",
        margin=0,
        visible=visible,
    )


class PlasmaShapeParams(Viewer):
    """Helper class containing parameters to parameterize the plasma shape."""

    a = param.Number(
        default=1.9,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[1, 2],
        label="Minor radius",
    )
    center_r = param.Number(
        default=6.2,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[5, 7],
        label="Plasma center radius",
    )
    center_z = param.Number(
        default=0.545, step=0.01, softbounds=[0, 1.5], label="Plasma center height"
    )
    kappa = param.Number(
        default=1.8,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[0, 3],
        label="Elongation",
    )
    delta = param.Number(
        default=0.43,
        step=0.01,
        bounds=(-1, 1),
        softbounds=[-1, 1],
        label="Triangularity",
    )
    rx = param.Number(
        default=5.089,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[4.5, 6],
        label="X-point radius",
    )
    zx = param.Number(
        default=-3.346, step=0.01, softbounds=[-4, -2], label="X-point height"
    )
    second_x_point = param.Boolean(default=False, label="Second x-point")
    rx_upper = param.Number(
        default=5.089,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[4.5, 6],
        label="Second x-point radius",
    )
    zx_upper = param.Number(
        default=3.346, step=0.01, softbounds=[2, 4], label="Second x-point height"
    )
    n_desired_bnd_points = param.Integer(
        default=100,
        bounds=(3, 5000),
        softbounds=[3, 200],
        label="Number of boundary points",
    )
    weight_enabled = param.Boolean(default=False, label="Emphasize a region")
    weight_position = param.Number(
        default=0, step=1, bounds=[0, 360], label="Position [deg]"
    )
    weight_spread = param.Number(
        default=15, step=0.5, softbounds=[1, 90], label="Spread [deg]"
    )
    weight_height = param.Integer(default=10, softbounds=[1, 1000], label="Max weight")
    extra_points_enabled = param.Boolean(
        default=False, label="Add additional weighted points"
    )
    extra_points_table = param.Parameter()

    def __init__(self, **params):
        super().__init__(**params)
        # The float sliders shown, so that their range can follow the machine
        self._sliders = {}

    def apply_machine_shape(self, values=True):
        """Start from the shape of the machine of the selected preset.

        Args:
            values: Whether to take its values, or only the ranges of the sliders.
        """
        shape = MACHINE_SHAPES.get(settings.nice.machine_preset)
        if shape is None:  # a custom machine, whose shape we cannot know
            return
        for name, (_, slider_range) in shape.items():
            if name in self.param:
                self.param[name].softbounds = slider_range
            if name in self._sliders:
                self._sliders[name].start, self._sliders[name].end = slider_range
        if not values:
            return
        self.param.update(
            **{name: value for name, (value, _) in shape.items() if name in self.param},
            second_x_point=False,
        )

    def _slider(self, n):
        """The widget of a parameter. The float sliders are kept, so that their
        range can follow the machine."""
        p = getattr(self.param, n)
        if isinstance(self.param[n], param.Boolean):
            return pn.widgets.Checkbox.from_param(p, sizing_mode="stretch_width")
        if isinstance(self.param[n], param.Integer):
            return FixedWidthEditableIntSlider.from_param(p, width=INPUT_WIDTH)
        self._sliders[n] = FormattedEditableFloatSlider.from_param(p, width=INPUT_WIDTH)
        return self._sliders[n]

    def fine_tuning(self, boundary_points):
        """The inputs that refine the boundary NICE is given.

        Args:
            boundary_points: Whether to show the number of boundary points, which only
                a parameterized boundary has, or a reactive expression of it.
        """
        _slider = self._slider
        return pn.Column(
            _group(
                "Boundary points",
                _slider("n_desired_bnd_points"),
                visible=boundary_points,
            ),
            _group(
                "Emphasized region",
                _slider("weight_enabled"),
                pn.FlexBox(
                    _slider("weight_position"),
                    _slider("weight_spread"),
                    _slider("weight_height"),
                    visible=self.param.weight_enabled.rx(),
                    sizing_mode="stretch_width",
                    margin=0,
                ),
            ),
            _group(
                "Extra points",
                _slider("extra_points_enabled"),
                pn.Row(
                    self.extra_points_table,
                    visible=self.param.extra_points_enabled.rx(),
                    sizing_mode="stretch_width",
                ),
            ),
            margin=0,
        )

    def __panel__(self):
        _slider = self._slider
        return pn.Column(
            _group(
                "Size and position",
                _slider("a"),
                _slider("center_r"),
                _slider("center_z"),
            ),
            _group(
                "Elongation and triangularity",
                _slider("kappa"),
                _slider("delta"),
                # A double null takes its shape from its x-points instead
                visible=self.param.second_x_point.rx.not_(),
            ),
            _group(
                "X-point",
                _slider("rx"),
                _slider("zx"),
                pn.Row(
                    pn.widgets.Checkbox.from_param(self.param.second_x_point),
                    pn.widgets.TooltipIcon(
                        value=(
                            "NICE inverse mode fits the target LCFS boundary points by "
                            "penalizing flux differences, but does not impose X-point "
                            "null constraints (∇ψ = 0). The resulting equilibrium is "
                            " not guaranteed to form two X-points and may produce only "
                            "1 or no X-points."
                        ),
                        align="center",
                        margin=(0, 0, 0, -10),
                    ),
                    sizing_mode="stretch_width",
                    margin=(0, 0, 5, 0),
                ),
                pn.FlexBox(
                    _slider("rx_upper"),
                    _slider("zx_upper"),
                    visible=self.param.second_x_point.rx(),
                    sizing_mode="stretch_width",
                    margin=0,
                ),
            ),
            margin=0,
        )
