"""The gaps between an ITER plasma and the first wall, as defined in DINA.

The definitions follow DINA-IMAS (src/scenario/g_gaps_rus.f, tools/GUI/captions.py):

- gaps 1 and 2 are the minimum distances from the reference strike points to the
  separatrix, which DINA only measures in the divertor phase, to the divertor legs;
- gaps 4 and 5 are the minimum distances from points on the wall to the boundary,
  towards the magnetic axis;
- Rmin and Rmax are the radii of the innermost and outermost boundary points, measured
  from r=0 at the height of those points.
"""

import numpy as np

from waveform_editor.shape_editor.gaps.base import MachineGaps, MeasuredGap
from waveform_editor.shape_editor.gaps.geometry import (
    closest_contour_point,
    closest_outline_point,
    geometric_centre,
    psi_contour,
)

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

    def gap_inputs(self, time_slice):
        quantities = time_slice.global_quantities
        return {
            "outline_r": time_slice.boundary.outline.r,
            "outline_z": time_slice.boundary.outline.z,
            "separatrix": psi_contour(time_slice, quantities.psi_boundary),
            "magnetic_axis": (quantities.magnetic_axis.r, quantities.magnetic_axis.z),
        }

    def measure(self, outline_r, outline_z, separatrix=(), magnetic_axis=None):
        """The gaps of an ITER plasma, with the points they are measured between.

        Args:
            outline_r: Radial coordinates of the plasma boundary.
            outline_z: Height coordinates of the plasma boundary.
            separatrix: The separatrix of a solved equilibrium, as (N, 2) arrays. Gaps 1
                and 2 are only measured to its legs, which do not close as they leave
                the domain.
            magnetic_axis: The (r, z) of the magnetic axis, the centre of the outline
                is used without one.
        """
        r, z = np.asarray(outline_r), np.asarray(outline_z)
        axis = magnetic_axis or geometric_centre(r, z)
        gaps = []

        diverted = any(np.linalg.norm(p[0] - p[-1]) > 1e-3 for p in separatrix)
        for sign, key in ((-1, "gap1"), (1, "gap2")):
            point = GAP_POINTS[key]
            if diverted:
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
