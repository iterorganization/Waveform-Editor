"""The gaps between a WEST plasma and the parts of the machine it is kept away from.

They are not stored in the machine description, so they are computed the way FEEQS
does, in Projects/WEST/Lib/plot_plasma_gaps_etc.m, from the geometry of WEST.
"""

import numpy as np

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


def compute_gaps(outline_r, outline_z, x_points):
    """The gaps of a WEST plasma, in metres.

    Args:
        outline_r: Radial coordinates of the plasma boundary.
        outline_z: Height coordinates of the plasma boundary.
        x_points: The (r, z) of each x-point of the equilibrium.

    Returns:
        Dict of gap name to distance, holding only the gaps that the boundary and the
        x-points given allow to be computed.
    """
    r, z = np.asarray(outline_r, dtype=float), np.asarray(outline_z, dtype=float)
    gaps = {}
    centre_r, radius = OUTER_ARC
    for name, height in (
        ("UROG", OUTER_GAP_HEIGHT),
        ("EROG", 0.0),
        ("LROG", -OUTER_GAP_HEIGHT),
    ):
        arc_r = centre_r + np.sqrt(radius**2 - height**2)
        boundary_r = _outboard_radius(r, z, height)
        if boundary_r is not None:
            gaps[name] = arc_r - boundary_r

    for name, divertor, below in (
        ("dXlow", LOWER_DIVERTOR, True),
        ("dXup", UPPER_DIVERTOR, False),
    ):
        x_point = _x_point(x_points, below)
        if x_point is not None:
            gaps[name] = _distance_to_line(x_point, *divertor)

    gaps["dbaffle"] = _distance_to_outline(BAFFLE, r, z)
    return gaps


def _outboard_radius(r, z, height):
    """The radius of the outboard side of the boundary at a height.

    Args:
        r: Radial coordinates of the boundary.
        z: Height coordinates of the boundary.
        height: The height to take the boundary at.

    Returns:
        The radius, or None when the boundary does not reach that height.
    """
    outboard = r > r.mean()
    r, z = r[outboard], z[outboard]
    if not len(z) or not z.min() <= height <= z.max():
        return None
    order = np.argsort(z)
    return float(np.interp(height, z[order], r[order]))


def _x_point(x_points, below):
    """The x-point below or above the midplane.

    Args:
        x_points: The (r, z) of each x-point.
        below: Whether to take the x-point below the midplane.

    Returns:
        The (r, z) of the x-point, or None when there is none on that side.
    """
    on_side = [point for point in x_points if (point[1] < 0) == below]
    return on_side[0] if on_side else None


def _distance_to_line(point, start, end):
    """The distance of a point to the line through two points.

    Args:
        point: The (r, z) to measure from.
        start: The (r, z) of a point of the line.
        end: The (r, z) of another point of the line.

    Returns:
        The distance.
    """
    point, start, end = (np.asarray(p, dtype=float) for p in (point, start, end))
    along = (end - start) / np.linalg.norm(end - start)
    to_point = point - start
    return float(np.linalg.norm(to_point - np.dot(to_point, along) * along))


def _distance_to_outline(point, r, z):
    """The distance of a point to the closest of the segments of an outline.

    Args:
        point: The (r, z) to measure from.
        r: Radial coordinates of the outline.
        z: Height coordinates of the outline.

    Returns:
        The distance.
    """
    starts = np.column_stack([r, z])
    ends = np.roll(starts, -1, axis=0)
    segments = ends - starts
    lengths = np.sum(segments**2, axis=1)
    # How far along each segment the point is, kept within the segment
    along = np.clip(
        np.sum((np.asarray(point, dtype=float) - starts) * segments, axis=1)
        / np.where(lengths > 0, lengths, 1),
        0,
        1,
    )
    closest = starts + along[:, None] * segments
    return float(np.min(np.linalg.norm(closest - point, axis=1)))
