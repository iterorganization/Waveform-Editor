"""The gaps between a WEST plasma and the parts of the machine it is kept away from.

They are not stored in the machine description, so they are computed the way FEEQS
does, in Projects/WEST/Lib/plot_plasma_gaps_etc.m, from the geometry of WEST.
"""

import math

import numpy as np

from waveform_editor.shape_editor.plasma_shape_calc import (
    Gap,
    closest_outline_point,
    project_point_to_line,
)

# The arc the outer radial gaps are measured to, which passes through r=3 m on the
# midplane, as (centre r, radius)
OUTER_ARC = (2.2, 0.8)
# The heights the upper and lower outer radial gaps are measured at
OUTER_GAP_HEIGHT = 0.25
# The divertor targets, as the two points of the line through each of them
LOWER_DIVERTOR = ((1.909, -0.5796), (2.362, -0.7624))
UPPER_DIVERTOR = ((1.9009, 0.5824), (2.446, 0.7995))
# The corner of the baffle the plasma is kept away from
BAFFLE = (2.381, -0.6757)

WEST_METADATA = {
    "UROG": ("UROG", "cm", "Upper radial outer gap"),
    "EROG": ("EROG", "cm", "Equatorial radial outer gap"),
    "LROG": ("LROG", "cm", "Lower radial outer gap"),
    "dXlow": ("dXlow", "cm", "Distance of the lower x-point to the divertor"),
    "dXup": ("dXup", "cm", "Distance of the upper x-point to the divertor"),
    "dbaffle": ("dbaffle", "cm", "Distance of the plasma to the baffle"),
}


def compute_gaps(outline_r, outline_z, x_points):
    """The gaps of a WEST plasma, in metres.

    Args:
        outline_r: Radial coordinates of the plasma boundary.
        outline_z: Height coordinates of the plasma boundary.
        x_points: The (r, z) of each x-point of the equilibrium.

    Returns:
        Dict of gap name to distance in metres.
    """
    r, z = np.asarray(outline_r, dtype=float), np.asarray(outline_z, dtype=float)
    gaps = {}
    centre_r, radius = OUTER_ARC
    for name, height in (
        ("UROG", OUTER_GAP_HEIGHT),
        ("EROG", 0.0),
        ("LROG", -OUTER_GAP_HEIGHT),
    ):
        boundary_r = _outboard_radius(r, z, height)
        if boundary_r is not None:
            gaps[name] = centre_r + np.sqrt(radius**2 - height**2) - boundary_r

    for name, divertor, below in (
        ("dXlow", LOWER_DIVERTOR, True),
        ("dXup", UPPER_DIVERTOR, False),
    ):
        x_point = _x_point(x_points, below)
        if x_point is not None:
            gaps[name] = project_point_to_line(x_point, *divertor)[1]

    gaps["dbaffle"] = closest_outline_point(BAFFLE, r, z)[1]
    return gaps


def compute_gap_geometry(outline_r, outline_z, x_points):
    """Compute measuring points and distance segments for WEST gaps."""
    if outline_r is None or outline_z is None or len(outline_r) == 0:
        return []

    r, z = np.asarray(outline_r, dtype=float), np.asarray(outline_z, dtype=float)
    items = []
    centre_r, radius = OUTER_ARC
    for name, height in (
        ("UROG", OUTER_GAP_HEIGHT),
        ("EROG", 0.0),
        ("LROG", -OUTER_GAP_HEIGHT),
    ):
        arc_r = float(centre_r + np.sqrt(radius**2 - height**2))
        boundary_r = _outboard_radius(r, z, height)
        if boundary_r is not None:
            dist = arc_r - boundary_r
            symbol, _, full_name = WEST_METADATA[name]
            items.append(
                {
                    "name": full_name,
                    "symbol": symbol,
                    "r_orig": arc_r,
                    "z_orig": height,
                    "r_target": boundary_r,
                    "z_target": height,
                    "distance": dist,
                    "distance_str": f"{dist * 100:.3g} cm",
                }
            )

    for name, divertor, below in (
        ("dXlow", LOWER_DIVERTOR, True),
        ("dXup", UPPER_DIVERTOR, False),
    ):
        x_point = _x_point(x_points, below)
        if x_point is not None:
            proj, dist = project_point_to_line(x_point, *divertor)
            symbol, _, full_name = WEST_METADATA[name]
            items.append(
                {
                    "name": full_name,
                    "symbol": symbol,
                    "r_orig": proj[0],
                    "z_orig": proj[1],
                    "r_target": float(x_point[0]),
                    "z_target": float(x_point[1]),
                    "distance": dist,
                    "distance_str": f"{dist * 100:.3g} cm",
                }
            )

    (target_r, target_z), dist = closest_outline_point(BAFFLE, r, z)
    symbol, _, full_name = WEST_METADATA["dbaffle"]
    items.append(
        {
            "name": full_name,
            "symbol": symbol,
            "r_orig": BAFFLE[0],
            "z_orig": BAFFLE[1],
            "r_target": target_r,
            "z_target": target_z,
            "distance": dist,
            "distance_str": f"{dist * 100:.3g} cm",
        }
    )

    return items


def _outboard_radius(r, z, height):
    """The radius of the outboard side of the boundary at a height."""
    outboard = r > r.mean()
    r, z = r[outboard], z[outboard]
    if not len(z) or not z.min() <= height <= z.max():
        return None
    order = np.argsort(z)
    return float(np.interp(height, z[order], r[order]))


def _x_point(x_points, below):
    """The x-point below or above the midplane."""
    on_side = [point for point in x_points if (point[1] < 0) == below]
    return on_side[0] if on_side else None


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
