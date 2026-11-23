"""The refinements of the boundary NICE is given, whichever way it is edited."""

import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.points_table import WeightedPointsTable
from waveform_editor.gui.shape_editor.shape_params import _group, param_input
from waveform_editor.shape_editor.plasma_shape_calc import (
    apply_point_weights,
    compute_gaussian_weights,
)


class ShapeRefinement(Viewer):
    """An emphasized region of the boundary, and weighted points added to it."""

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
    extra_points_table = param.ClassSelector(
        class_=WeightedPointsTable, default=WeightedPointsTable()
    )

    def __init__(self, **params):
        super().__init__(**params)
        self.panel = pn.Column(
            _group(
                "Emphasized region",
                param_input(self.param.weight_enabled),
                pn.FlexBox(
                    param_input(self.param.weight_position),
                    param_input(self.param.weight_spread),
                    param_input(self.param.weight_height),
                    visible=self.param.weight_enabled.rx(),
                    sizing_mode="stretch_width",
                    margin=0,
                ),
            ),
            _group(
                "Extra points",
                param_input(self.param.extra_points_enabled),
                pn.Row(
                    self.extra_points_table,
                    visible=self.param.extra_points_enabled.rx(),
                    sizing_mode="stretch_width",
                ),
            ),
            margin=0,
        )

    def refine(self, r, z):
        """The outline NICE is given from a boundary.

        Args:
            r: Radial coordinates of the boundary.
            z: Height coordinates of the boundary.

        Returns:
            Tuple of (r, z, weights) of the outline, with the weight of each point of
            the boundary, or None when no region is emphasized.
        """
        weights = None
        if self.weight_enabled:
            weights = compute_gaussian_weights(
                r, z, self.weight_position, self.weight_spread, self.weight_height
            )
            r, z = apply_point_weights(r, z, weights)
        if self.extra_points_enabled:
            # Last, as NICE measures every point against the first one, so repeats
            # of the first point would cancel out
            extra_r, extra_z = self.extra_points_table.get_outline_coordinates()
            if extra_r:
                r, z = r + extra_r, z + extra_z
        return r, z, weights

    def __panel__(self):
        return self.panel
