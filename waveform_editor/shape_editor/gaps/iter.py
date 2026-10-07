"""The gaps between an ITER plasma and the first wall, as defined in DINA.

The definitions follow DINA-IMAS (src/scenario/g_gaps_rus.f, tools/GUI/captions.py):

- gaps 1 and 2 are the minimum distances from the reference strike points to the
  separatrix, which DINA only measures in the divertor phase, to the divertor legs;
- gaps 4 and 5 are the minimum distances from points on the wall to the boundary,
  towards the magnetic axis;
- Rmin and Rmax are the radii of the innermost and outermost boundary points, measured
  from r=0 at the height of those points.
"""

import math

import numpy as np

from waveform_editor.shape_editor.gaps.base import MachineGaps, MeasuredGap
from waveform_editor.shape_editor.gaps.geometry import (
    closest_contour_point,
    closest_outline_point,
    geometric_centre,
    psi_contour,
)
from waveform_editor.shape_editor.plasma_shape_calc import Gap

# The points the gaps are measured from, in metres (r, z)
GAP_POINTS = {
    "gap1": (4.2230, -3.7920),
    "gap2": (5.5650, -4.4040),
    "gap4": (7.5095, 2.9971),
    "gap5": (5.3315, 4.5804),
}


class IterGaps(MachineGaps):
    """The gaps of an ITER plasma, as DINA computes them."""

    GAP_METADATA = {
        "gap1": ("g₁", "cm", "Inner divertor leg gap"),
        "gap2": ("g₂", "cm", "Outer divertor leg gap"),
        "gap4": ("g₄", "cm", "Point at 2 o'clock gap"),
        "gap5": ("g₅", "cm", "Uppest boundary point gap"),
        "Rmin": ("Rₘᵢₙ", "m", "Inboard boundary radius"),
        "Rmax": ("Rₘₐₓ", "m", "Outboard boundary radius"),
    }

    def default_gaps(self):
        """Rmin and Rmax are measured from r=0, at the height of the innermost and
        outermost point."""
        return [
            Gap("Inner divertor leg (g₁)", 4.2230, -3.7920, math.radians(-65.0), 0.0),
            Gap("Outer divertor leg (g₂)", 5.5650, -4.4040, math.radians(-150.0), 0.0),
            Gap("Point at 2 o'clock (g₄)", 7.5095, 2.9971, math.radians(135.0), 0.228),
            Gap(
                "Uppest boundary point (g₅)", 5.3315, 4.5804, math.radians(90.0), 0.596
            ),
            Gap("Inboard mid-plane (Rmin)", 0.0, 0.7777, 0.0, 4.2099),
            Gap("Outboard mid-plane (Rmax)", 0.0, 0.4665, 0.0, 8.2006),
        ]

    def gap_inputs(self, time_slice):
        """Takes the separatrix up to the top of the plasma, as DINA does, only for a
        diverted plasma, with an x-point on its boundary."""
        quantities = time_slice.global_quantities
        outline = time_slice.boundary.outline
        diverted = any(
            node.critical_type == 1 and np.isclose(node.psi, quantities.psi_boundary)
            for node in time_slice.contour_tree.node
        )
        pieces = psi_contour(time_slice, quantities.psi_boundary) if diverted else []
        return {
            "outline_r": outline.r,
            "outline_z": outline.z,
            "separatrix": [p for p in pieces if p[:, 1].min() <= np.max(outline.z)],
            "magnetic_axis": (quantities.magnetic_axis.r, quantities.magnetic_axis.z),
        }

    def measure(self, outline_r, outline_z, separatrix=(), magnetic_axis=None):
        """The gaps of an ITER plasma, with the points they are measured between.

        Args:
            outline_r: Radial coordinates of the plasma boundary.
            outline_z: Height coordinates of the plasma boundary.
            separatrix: The separatrix of a diverted solved equilibrium, as (N, 2)
                arrays. Gaps 1 and 2 are only measured with one.
            magnetic_axis: The (r, z) of the magnetic axis, the centre of the outline
                is used without one.
        """
        r, z = np.asarray(outline_r), np.asarray(outline_z)
        axis = magnetic_axis or geometric_centre(r, z)
        gaps = []

        for sign, key in ((-1, "gap1"), (1, "gap2")):
            point = GAP_POINTS[key]
            if separatrix:
                target, distance = closest_contour_point(point, separatrix)
                distance *= sign * _side_of_axis(target, point, axis)
                gaps.append(MeasuredGap(key, point, target, distance))
            else:
                gaps.append(MeasuredGap(key, point, point, None))

        for key in ("gap4", "gap5"):
            point = GAP_POINTS[key]
            target, distance = closest_outline_point(point, r, z, facing=axis)
            if target is not None:
                gaps.append(MeasuredGap(key, point, target, distance))

        for key, i in (("Rmin", np.argmin(r)), ("Rmax", np.argmax(r))):
            gaps.append(MeasuredGap(key, (0.0, z[i]), (r[i], z[i]), r[i]))
        return gaps


def _side_of_axis(target, point, axis):
    """Which side of the axis the closest point is on, as 1 or -1, which DINA signs
    gaps 1 and 2 with (g_gaps_rus.f)."""
    r_target, z_target = np.subtract(target, axis)
    r_point, z_point = np.subtract(point, axis)
    return 1.0 if r_target * z_point - z_target * r_point >= 0 else -1.0
