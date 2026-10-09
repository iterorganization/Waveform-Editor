"""The geometry the gaps are measured with."""

from functools import lru_cache

import numpy as np
from matplotlib.figure import Figure
from matplotlib.tri import Triangulation
from scipy.interpolate import PchipInterpolator


def closest_outline_point(point, r, z, is_closed=True, facing=None):
    """The point of an outline closest to a point.

    Args:
        point: The (r, z) to measure from.
        r: Radial coordinates of the outline.
        z: Height coordinates of the outline.
        is_closed: Whether the outline closes on itself.
        facing: An (r, z), such as the magnetic axis, that the closest point must lie
            towards, as DINA measures its gaps 4 and 5.

    Returns:
        Tuple of ((r, z) of the closest point, distance), or (None, inf) if no point
        lies towards ``facing``.
    """
    point = np.asarray(point)
    starts = np.column_stack([r, z])
    ends = np.roll(starts, -1, axis=0) if is_closed else starts[1:]
    starts = starts if is_closed else starts[:-1]
    segments = ends - starts
    lengths = np.sum(segments**2, axis=1)
    projections = np.sum((point - starts) * segments, axis=1)
    along = np.divide(
        projections, lengths, out=np.zeros_like(lengths), where=lengths > 0
    )
    along = np.clip(along, 0, 1)
    feet = starts + along[:, None] * segments
    distances = np.linalg.norm(feet - point, axis=1)
    if facing is not None:
        distances[(feet - point) @ (np.asarray(facing) - point) < 0] = np.inf
    i = np.argmin(distances)
    if np.isinf(distances[i]):
        return None, np.inf
    return tuple(feet[i]), distances[i]


def closest_contour_point(point, pieces):
    """The point closest to a point on any piece of a contour.

    Args:
        point: The (r, z) to measure from.
        pieces: The contour, as (N, 2) arrays of (r, z), each an open polyline.

    Returns:
        Tuple of ((r, z) of the closest point, distance).
    """
    return min(
        (closest_outline_point(point, *piece.T, is_closed=False) for piece in pieces),
        key=lambda found: found[1],
    )


def project_point_to_line(point, start, end):
    """The foot of a point on the line through start and end, and its distance."""
    point, start, end = (np.asarray(v) for v in (point, start, end))
    along = (end - start) / np.linalg.norm(end - start)
    foot = start + np.dot(point - start, along) * along
    return tuple(foot), np.linalg.norm(point - foot)


def interpolate_branch(x, y, at, branch):
    """The y of a branch of an outline at x, with pchip as FEEQS does.

    Args:
        x: The coordinates of the outline along which to interpolate.
        y: The coordinates of the outline to interpolate.
        at: The x to find the y at.
        branch: Which points of the outline form the branch, along which y is a
            function of x.

    Returns:
        The y at ``at``, or None if the branch does not reach it.
    """
    x, unique = np.unique(x[branch], return_index=True)
    if len(x) < 2 or not x[0] <= at <= x[-1]:
        return None
    return PchipInterpolator(x, y[branch][unique])(at).item()


def geometric_centre(r, z):
    """The centre of the bounding box of an outline."""
    return (np.min(r) + np.max(r)) / 2, (np.min(z) + np.max(z)) / 2


@lru_cache(maxsize=1)
def _triangulation(r, z):
    """The triangulation of the nodes of a mesh, given as bytes, which is the same
    for every result of a machine."""
    return Triangulation(np.frombuffer(r), np.frombuffer(z))


def flux_contours(time_slice, levels):
    """The contours of the poloidal flux on the GGD NICE fills.

    Args:
        time_slice: The equilibrium time slice.
        levels: The number of contours, or the fluxes to contour.

    Returns:
        The matplotlib TriContourSet.
    """
    ggd = time_slice.ggd[0]
    triangulation = _triangulation(ggd.r[0].values.tobytes(), ggd.z[0].values.tobytes())
    return Figure().add_subplot().tricontour(triangulation, ggd.psi[0].values, levels)


def psi_contour(time_slice, level):
    """The contour of the poloidal flux on the GGD NICE fills, at a level.

    Args:
        time_slice: The equilibrium time slice.
        level: The flux to contour.

    Returns:
        List of (N, 2) arrays of (r, z), one per piece of the contour.
    """
    contour = flux_contours(time_slice, [level])
    return [np.asarray(piece) for piece in contour.allsegs[0] if len(piece) > 1]
