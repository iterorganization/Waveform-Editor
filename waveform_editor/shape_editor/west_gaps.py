"""The gaps between a WEST plasma and the parts of the machine it is kept away from.

They are not stored in the machine description, so they are computed the way FEEQS
does, in Projects/WEST/Lib/plot_plasma_gaps_etc.m, from the geometry of WEST.
"""

import math

import numpy as np
from matplotlib.path import Path

from waveform_editor.shape_editor.plasma_shape_calc import (
    Gap,
    closest_outline_point,
    geometric_centre,
    interpolate_branch,
    project_point_to_line,
    psi_contour,
)

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
# FEEQS only takes the x-points inside this region
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

WEST_METADATA = {
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


def gap_inputs(time_slice):
    """The arguments to compute the gaps of a solved equilibrium with.

    Args:
        time_slice: The equilibrium time slice.

    Returns:
        Dict of the keyword arguments of compute_gaps and compute_gap_geometry.
    """
    axis = time_slice.global_quantities.magnetic_axis
    return {
        "outline_r": time_slice.boundary.outline.r,
        "outline_z": time_slice.boundary.outline.z,
        "x_points": [
            (float(node.r), float(node.z), float(node.psi))
            for node in time_slice.contour_tree.node
            if int(node.critical_type) == 1
        ],
        "magnetic_axis": (
            float(axis.r),
            float(axis.z),
            float(time_slice.global_quantities.psi_axis),
        ),
        "contour": lambda level: psi_contour(time_slice, level),
    }


def compute_gaps(outline_r, outline_z, x_points, magnetic_axis=None, contour=None):
    """The gaps of a WEST plasma, in metres.

    Args:
        outline_r: Radial coordinates of the plasma boundary.
        outline_z: Height coordinates of the plasma boundary.
        x_points: The (r, z) or (r, z, psi) of each x-point of the equilibrium.
        magnetic_axis: The (r, z, psi) of the magnetic axis, the centre of the
            outline is used without one.
        contour: Function returning the contour of the flux at a level, as a list
            of (N, 2) arrays, for the gaps measured to the separatrix with its legs.

    Returns:
        Dict of gap name to distance in metres.
    """
    items = compute_gap_geometry(outline_r, outline_z, x_points, magnetic_axis, contour)
    return {item["key"]: item["distance"] for item in items}


def compute_gap_geometry(
    outline_r, outline_z, x_points, magnetic_axis=None, contour=None
):
    """The gaps of a WEST plasma, as computed in FEEQS, together with the points they
    are measured between.

    Args:
        outline_r: Radial coordinates of the plasma boundary.
        outline_z: Height coordinates of the plasma boundary.
        x_points: The (r, z) or (r, z, psi) of each x-point of the equilibrium.
        magnetic_axis: The (r, z, psi) of the magnetic axis, the centre of the
            outline is used without one.
        contour: Function returning the contour of the flux at a level, as a list
            of (N, 2) arrays, for the gaps measured to the separatrix with its legs.

    Returns:
        List of dicts, one per gap that could be measured.
    """
    if outline_r is None or outline_z is None or len(outline_r) == 0:
        return []
    r, z = np.asarray(outline_r, dtype=float), np.asarray(outline_z, dtype=float)
    axis = magnetic_axis[:2] if magnetic_axis is not None else geometric_centre(r, z)
    psi_axis = magnetic_axis[2] if magnetic_axis is not None else None
    x_points = _select_x_points(x_points, psi_axis)
    items = []

    def add(key, orig, target, distance):
        symbol, _, name = WEST_METADATA[key]
        items.append(
            {
                "key": key,
                "name": name,
                "symbol": symbol,
                "r_orig": float(orig[0]),
                "z_orig": float(orig[1]),
                "r_target": float(target[0]),
                "z_target": float(target[1]),
                "distance": float(distance),
                "distance_str": f"{distance * 100:.3g} cm",
            }
        )

    # The outer radial gaps, each on its own quarter of the boundary
    centre_r, radius = OUTER_ARC
    for key, height, theta_range in (
        ("UROG", OUTER_GAP_HEIGHT, (0, math.pi / 2)),
        ("EROG", 0.0, (-math.pi / 2, math.pi / 2)),
        ("LROG", -OUTER_GAP_HEIGHT, (-math.pi / 2, 0)),
    ):
        wall_r = centre_r + math.sqrt(radius**2 - height**2)
        boundary_r = interpolate_branch(r, z, axis, height, theta_range)
        if boundary_r is not None:
            add(key, (wall_r, height), (boundary_r, height), wall_r - boundary_r)

    # The radial inner gap, on the inboard side within pi/16 of the midplane. FEEQS
    # reports it as wall minus boundary, which is negative; it is a clearance here.
    rig_r, rig_z = RIG_POINT
    wedge = (math.pi - math.pi / 16, -math.pi + math.pi / 16)
    boundary_r = interpolate_branch(r, z, axis, rig_z, wedge)
    if boundary_r is not None:
        add("RIG", RIG_POINT, (boundary_r, rig_z), boundary_r - rig_r)

    # The top gaps, measured down to the upper half of the boundary
    for key, (wall_r, wall_z) in (("TIG", TIG_POINT), ("TOG", TOG_POINT)):
        boundary_z = interpolate_branch(r, z, axis, wall_r, (0, math.pi), along="r")
        if boundary_z is not None:
            add(key, (wall_r, wall_z), (wall_r, boundary_z), wall_z - boundary_z)

    for key, divertor, below in (
        ("dXlow", LOWER_DIVERTOR, True),
        ("dXup", UPPER_DIVERTOR, False),
    ):
        on_side = [point for point in x_points if (point[1] < 0) == below]
        if on_side:
            foot, distance = project_point_to_line(on_side[0][:2], *divertor)
            add(key, foot, on_side[0][:2], distance)

    # FEEQS measures the baffle to the separatrix with its legs, which only a solved
    # equilibrium has; a desired boundary is its own separatrix
    separatrix, is_closed = [np.column_stack([r, z])], True
    if contour is not None and x_points and len(x_points[0]) > 2:
        pieces = contour(x_points[0][2])
        if pieces:
            # Contour pieces are open polylines; a closed one repeats its first point
            separatrix, is_closed = pieces, False
    best = None
    for piece in separatrix:
        target, distance = closest_outline_point(
            BAFFLE, piece[:, 0], piece[:, 1], is_closed=is_closed
        )
        if best is None or distance < best[1]:
            best = target, distance
    add("dbaffle", BAFFLE, best[0], best[1])

    # The distance between the separatrices of a double null on the outboard midplane
    if contour is not None and len(x_points) == 2 and len(x_points[1]) > 2:
        radii = [
            _outboard_midplane_radius(contour(point[2]), axis) for point in x_points
        ]
        if None not in radii:
            first, second = radii
            add("dRsep", (first, 0.0), (second, 0.0), second - first)

    return items


def _select_x_points(x_points, psi_axis):
    """The x-points FEEQS takes: those inside its search region, at most two, the
    one of the first separatrix first.

    The first separatrix is the one closest in flux to the magnetic axis, which FEEQS
    finds by sorting on psi in its own sign convention.
    """
    inside = [
        tuple(float(v) for v in point)
        for point in x_points
        if X_SEARCH_REGION.contains_point(point[:2])
    ]
    if psi_axis is not None and all(len(point) > 2 for point in inside):
        inside.sort(key=lambda point: abs(point[2] - psi_axis))
    return inside[:2]


def _outboard_midplane_radius(pieces, axis):
    """The radius at z=0 of the outboard side of a contour."""
    if not pieces:
        return None
    points = np.concatenate(pieces)
    return interpolate_branch(
        points[:, 0], points[:, 1], axis, 0.0, (-math.pi / 2, math.pi / 2)
    )


def get_default_west_gaps():
    """Return default Gap definitions for WEST based on machine geometry."""
    return [
        Gap("Upper radial outer gap (UROG)", 2.9599, 0.25, math.pi, 0.06),
        Gap("Equatorial radial outer gap (EROG)", 3.0000, 0.0, math.pi, 0.08),
        Gap("Lower radial outer gap (LROG)", 2.9599, -0.25, math.pi, 0.06),
        Gap(
            "Lower x-point to divertor (dXlow)",
            2.1350,
            -0.6710,
            -math.radians(68.0),
            0.05,
        ),
        Gap(
            "Upper x-point to divertor (dXup)", 2.1730, 0.6910, math.radians(68.0), 0.10
        ),
        Gap(
            "Distance to baffle (dbaffle)", 2.3810, -0.6757, -math.radians(135.0), 0.04
        ),
    ]
