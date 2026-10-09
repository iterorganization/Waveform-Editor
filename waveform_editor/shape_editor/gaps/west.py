"""The gaps between a WEST plasma and the parts of the machine it is kept away from.

They are not stored in the machine description, so they are computed the way FEEQS
does, in Projects/WEST/Lib/plot_plasma_gaps_etc.m, from the geometry of WEST.
"""

import math

import numpy as np
from matplotlib.path import Path

from waveform_editor.shape_editor.gaps.base import MachineGaps, MeasuredGap
from waveform_editor.shape_editor.gaps.geometry import (
    closest_contour_point,
    closest_outline_point,
    geometric_centre,
    interpolate_branch,
    project_point_to_line,
    psi_contour,
)
from waveform_editor.shape_editor.plasma_shape_calc import Gap

# The arc the outer radial gaps are measured to, which passes through r=3 m on the
# midplane, as (centre r, radius)
OUTER_ARC = (2.2, 0.8)
# The heights the upper and lower outer radial gaps are measured at
OUTER_GAP_HEIGHT = 0.25
# The inner wall the radial inner gap is measured to, on the midplane
RIG_POINT = (1.834, 0.0)
# The points above the plasma the top inner and outer gaps are measured to
TIG_POINT = (2.132, 0.672)
TOG_POINT = (2.456, 0.749)
# The divertor targets, as the two points of the line through each of them
LOWER_DIVERTOR = ((1.909, -0.5796), (2.362, -0.7624))
UPPER_DIVERTOR = ((1.9009, 0.5824), (2.446, 0.7995))
# The corner of the baffle the plasma is kept away from
BAFFLE = (2.381, -0.6757)
# The region FEEQS looks for x-points in
X_SEARCH_REGION = Path(
    [
        (1.956, -0.6582),
        (2.315, -0.8031),
        (2.6, -0.8031),
        (2.6, 0.8018),
        (2.304, 0.8018),
        (1.956, 0.6611),
    ]
)


class WestGaps(MachineGaps):
    """The gaps of a WEST plasma, as FEEQS computes them."""

    GAP_METADATA = {
        "UROG": ("UROG", "cm", "Upper radial outer gap"),
        "EROG": ("EROG", "cm", "Equatorial radial outer gap"),
        "LROG": ("LROG", "cm", "Lower radial outer gap"),
        "RIG": ("RIG", "cm", "Radial inner gap"),
        "TIG": ("TIG", "cm", "Top inner gap"),
        "TOG": ("TOG", "cm", "Top outer gap"),
        "dXlow": ("dXlow", "cm", "Distance of the lower x-point to the divertor"),
        "dXup": ("dXup", "cm", "Distance of the upper x-point to the divertor"),
        "dbaffle": ("dbaffle", "cm", "Distance of the plasma to the baffle"),
        "dRsep": (
            "dRsep",
            "cm",
            "Distance between the second and first separatrix on the outboard midplane",
        ),
    }

    def default_gaps(self):
        return [
            Gap("Upper radial outer gap (UROG)", 2.9599, 0.25, math.pi, 0.06),
            Gap("Equatorial radial outer gap (EROG)", 3.0000, 0.0, math.pi, 0.08),
            Gap("Lower radial outer gap (LROG)", 2.9599, -0.25, math.pi, 0.06),
            Gap(
                "Lower x-point to divertor (dXlow)",
                2.135,
                -0.671,
                -math.radians(68.0),
                0.05,
            ),
            Gap(
                "Upper x-point to divertor (dXup)",
                2.173,
                0.691,
                math.radians(68.0),
                0.10,
            ),
            Gap(
                "Distance to baffle (dbaffle)",
                2.381,
                -0.6757,
                -math.radians(135.0),
                0.04,
            ),
        ]

    def gap_inputs(self, time_slice):
        """Orders the x-points as FEEQS does, that of the first separatrix, closest in
        flux to the magnetic axis, first."""
        quantities = time_slice.global_quantities
        axis = quantities.magnetic_axis
        x_points = [
            (node.r, node.z, node.psi)
            for node in time_slice.contour_tree.node
            if node.critical_type == 1
        ]
        x_points.sort(key=lambda point: abs(point[2] - quantities.psi_axis))
        return {
            "outline_r": time_slice.boundary.outline.r,
            "outline_z": time_slice.boundary.outline.z,
            "x_points": np.array(x_points),
            "magnetic_axis": (axis.r, axis.z),
            "contour": lambda level: psi_contour(time_slice, level),
        }

    def shape_inputs(self, x_points):
        return {"x_points": x_points}

    def measure(self, outline_r, outline_z, x_points, magnetic_axis=None, contour=None):
        """The gaps of a WEST plasma, with the points they are measured between.

        As in FEEQS, each gap is measured on the branch of the boundary selected by
        its angle about the magnetic axis, using at most two x-points inside the search
        region. Unlike FEEQS, RIG is a positive clearance, and dbaffle is measured to
        the boundary when there is no contour of the separatrix with its legs.

        Args:
            outline_r: Radial coordinates of the plasma boundary.
            outline_z: Height coordinates of the plasma boundary.
            x_points: The (r, z) of each x-point, with its psi for a solved
                equilibrium, the one of the first separatrix first.
            magnetic_axis: The (r, z) of the magnetic axis, the centre of the outline
                is used without one.
            contour: Function returning the contour of the flux at a level, as a list
                of (N, 2) arrays, which only a solved equilibrium has.
        """
        r, z = np.asarray(outline_r), np.asarray(outline_z)
        axis = magnetic_axis or geometric_centre(r, z)
        x_points = [p for p in x_points if X_SEARCH_REGION.contains_point(p[:2])][:2]
        gaps = []

        theta = np.arctan2(z - axis[1], r - axis[0])

        centre_r, radius = OUTER_ARC
        for key, height, branch in (
            ("UROG", OUTER_GAP_HEIGHT, (theta > 0) & (theta < math.pi / 2)),
            ("EROG", 0.0, abs(theta) < math.pi / 2),
            ("LROG", -OUTER_GAP_HEIGHT, (theta < 0) & (theta > -math.pi / 2)),
        ):
            wall_r = centre_r + math.sqrt(radius**2 - height**2)
            boundary_r = interpolate_branch(z, r, height, branch)
            if boundary_r is not None:
                distance = wall_r - boundary_r
                gaps.append(
                    MeasuredGap(key, (wall_r, height), (boundary_r, height), distance)
                )

        rig_r, rig_z = RIG_POINT
        boundary_r = interpolate_branch(
            z, r, rig_z, abs(theta) > math.pi - math.pi / 16
        )
        if boundary_r is not None:
            gaps.append(
                MeasuredGap("RIG", RIG_POINT, (boundary_r, rig_z), boundary_r - rig_r)
            )

        for key, (wall_r, wall_z) in (("TIG", TIG_POINT), ("TOG", TOG_POINT)):
            boundary_z = interpolate_branch(r, z, wall_r, theta > 0)
            if boundary_z is not None:
                distance = wall_z - boundary_z
                gaps.append(
                    MeasuredGap(key, (wall_r, wall_z), (wall_r, boundary_z), distance)
                )

        for key, divertor, below in (
            ("dXlow", LOWER_DIVERTOR, True),
            ("dXup", UPPER_DIVERTOR, False),
        ):
            on_side = [point for point in x_points if (point[1] < 0) == below]
            if on_side:
                x_point = tuple(on_side[0][:2])
                foot, distance = project_point_to_line(x_point, *divertor)
                gaps.append(MeasuredGap(key, foot, x_point, distance))

        if contour is not None and x_points:
            target, distance = closest_contour_point(BAFFLE, contour(x_points[0][2]))
        else:
            target, distance = closest_outline_point(BAFFLE, r, z)
        gaps.append(MeasuredGap("dbaffle", BAFFLE, target, distance))

        if contour is not None and len(x_points) == 2:
            first, second = (
                _outboard_midplane_radius(contour(point[2]), axis) for point in x_points
            )
            if first is not None and second is not None:
                gaps.append(
                    MeasuredGap("dRsep", (first, 0.0), (second, 0.0), second - first)
                )
        return gaps


def _outboard_midplane_radius(pieces, axis):
    """The radius at z=0 of the outboard side of a contour."""
    r, z = np.concatenate(pieces).T
    outboard = abs(np.arctan2(z - axis[1], r - axis[0])) < math.pi / 2
    return interpolate_branch(z, r, 0.0, outboard)
