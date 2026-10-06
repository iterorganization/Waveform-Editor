"""Pure geometry calculations for the plasma shape, with no Panel dependency."""

import math
from dataclasses import dataclass

import numpy as np


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


def _divertor_leg(midplane, x_point, n_points):
    """The points of a divertor leg, which runs from a point on the midplane to the
    x-point along the arc that leaves the midplane vertically.

    Args:
        midplane: The (r, z) the leg starts at, on the inner or outer midplane.
        x_point: The (r, z) of the x-point the leg ends at.
        n_points: Number of points of the leg, excluding its two ends.

    Returns:
        List of (r, z) along the leg, from the midplane towards the x-point.
    """
    (r_start, z_start), (rx, zx) = midplane, x_point
    dr, dz = rx - r_start, zx - z_start
    fractions = [(i + 1) / (n_points + 1) for i in range(n_points)]
    if abs(dr) < abs(dz) * 1e-6:  # the x-point is straight above or below
        return [(r_start + f * dr, z_start + f * dz) for f in fractions]

    # The centre is where the bisector of the two points meets the midplane
    r_centre = r_start + (dr**2 + dz**2) / (2 * dr)
    radius = abs(r_centre - r_start)
    angle_start = math.atan2(0.0, r_start - r_centre)
    angle_x = math.atan2(zx - z_start, rx - r_centre)
    # The short way around, so that the leg does not run around the plasma
    sweep = (angle_x - angle_start + math.pi) % (2 * math.pi) - math.pi
    return [
        (
            r_centre + radius * math.cos(angle_start + f * sweep),
            z_start + radius * math.sin(angle_start + f * sweep),
        )
        for f in fractions
    ]


def compute_outline_from_params(
    a,
    center_r,
    center_z,
    kappa,
    delta,
    rx,
    zx,
    n_desired_bnd_points,
    rx_upper=None,
    zx_upper=None,
):
    """Compute plasma boundary outline from parameterized shape inputs.

    Adapted from NICE, by Blaise Faugeras:
    https://gitlab.inria.fr/blfauger/nice

    Args:
        a: Minor radius.
        center_r: Plasma center major radius.
        center_z: Plasma center height.
        kappa: Elongation.
        delta: Triangularity.
        rx: X-point major radius.
        zx: X-point height.
        n_desired_bnd_points: Number of desired boundary points.
        rx_upper: Major radius of a second x-point, for a double null plasma.
        zx_upper: Height of that second x-point.

    Returns:
        Tuple of (outline_r, outline_z) coordinate lists.
    """
    points = []
    r0, z0 = center_r, center_z
    nb_desired_point = n_desired_bnd_points

    # Calculate point distribution
    nb_point1 = (nb_desired_point - 1) // 2
    rem1 = (nb_desired_point - 1) % 2
    nb_point2 = (rem1 + nb_point1) // 2
    nb_point3 = nb_point2
    if (rem1 + nb_point1) % 2 == 1:
        nb_point1 += 1

    if rx_upper is not None:
        # A double null is four legs between the midplane and the two x-points
        x_points = [(rx, zx), (rx_upper, zx_upper)]
        n_leg = (nb_desired_point - len(x_points) - 2) // 4
        points += [(r0 - a, z0), (r0 + a, z0), *x_points]
        for x_point in x_points:
            points += _divertor_leg((r0 - a, z0), x_point, n_leg)
            points += _divertor_leg((r0 + a, z0), x_point, n_leg)
    else:
        # First segment: main plasma shape
        theta1 = math.pi / (nb_point1 - 1)
        asin_delta = math.asin(delta)
        for i in range(nb_point1):
            theta = i * theta1
            r = r0 + a * math.cos(theta + asin_delta * math.sin(theta))
            z = z0 + a * kappa * math.sin(theta)
            points.append((r, z))

        # Second and third arc: the divertor legs
        points += _divertor_leg((r0 - a, z0), (rx, zx), nb_point2)
        points += _divertor_leg((r0 + a, z0), (rx, zx), nb_point3)

        points.append((rx, zx))

    # Sort points by angle from centroid
    mean_r = sum(p[0] for p in points) / len(points)
    mean_z = sum(p[1] for p in points) / len(points)
    points.sort(key=lambda p: math.atan2(p[1] - mean_z, p[0] - mean_r))

    return [p[0] for p in points], [p[1] for p in points]


def compute_gaussian_weights(r, z, position, spread, height):
    """Compute an integer weight for each boundary point, following a circular
    Gaussian centred at `position` degrees around the boundary. Angles are measured
    at the boundary centroid, the same way the points are ordered.

    Args:
        r: Radial coordinates of the boundary points.
        z: Height coordinates of the boundary points.
        position: Centre of the emphasized region, in degrees.
        spread: Standard deviation of the Gaussian, in degrees.
        height: Weight at the centre of the emphasized region.

    Returns:
        List of integer weights, one per boundary point.
    """
    r = np.asarray(r)
    z = np.asarray(z)
    if r.size == 0:
        return []

    spread = max(spread, 1e-6)
    angle = np.degrees(np.arctan2(z - z.mean(), r - r.mean()))
    # The boundary is a closed curve, so the far side wraps around
    distance = np.abs((angle - position + 180) % 360 - 180)
    weights = 1 + (height - 1) * np.exp(-0.5 * (distance / spread) ** 2)
    return np.maximum(np.round(weights), 1).astype(int).tolist()


def apply_point_weights(r, z, weights):
    """Duplicate each boundary point according to its weight.

    Args:
        r: Radial coordinates of the boundary points.
        z: Height coordinates of the boundary points.
        weights: Integer weight for each point.

    Returns:
        Tuple of (weighted_r, weighted_z) with points duplicated per weight.
    """
    return np.repeat(r, weights).tolist(), np.repeat(z, weights).tolist()


def update_outline_from_gaps(gaps):
    """Compute outline coordinates from a list of Gap objects.

    Args:
        gaps: List of Gap objects.

    Returns:
        Tuple of (outline_r, outline_z), or (None, None) if gaps is empty.
    """
    if not gaps:
        return None, None
    return [gap.r_sep for gap in gaps], [gap.z_sep for gap in gaps]


def closest_outline_point(point, r, z, is_closed=True):
    """Find closest point on outline to a given (r, z) coordinate."""
    starts = np.column_stack([r, z])
    if len(starts) == 0:
        return (0.0, 0.0), float("inf")
    if len(starts) == 1:
        return (float(starts[0, 0]), float(starts[0, 1])), float(
            np.linalg.norm(starts[0] - point)
        )
    ends = np.roll(starts, -1, axis=0) if is_closed else starts[1:]
    if not is_closed:
        starts = starts[:-1]
    segs = ends - starts
    lens = np.sum(segs**2, axis=1)
    along = np.clip(
        np.sum((np.asarray(point, float) - starts) * segs, axis=1)
        / np.where(lens > 0, lens, 1),
        0,
        1,
    )
    closest = starts + along[:, None] * segs
    dists = np.linalg.norm(closest - point, axis=1)
    idx = int(np.argmin(dists))
    return (float(closest[idx, 0]), float(closest[idx, 1])), float(dists[idx])


def project_point_to_line(point, start, end):
    """Project a point onto the line passing through start and end."""
    start, end = np.asarray(start, float), np.asarray(end, float)
    along = (end - start) / np.linalg.norm(end - start)
    to_pt = np.asarray(point, float) - start
    proj = start + np.dot(to_pt, along) * along
    dist = float(np.linalg.norm(to_pt - np.dot(to_pt, along) * along))
    return (float(proj[0]), float(proj[1])), dist


def closest_point_facing(point, r, z, axis, is_closed=True):
    """The closest point on an outline that lies on the side of the axis, as DINA
    measures its gaps 4 and 5: the foot must satisfy (foot - point).(axis - point) >= 0,
    so a branch behind the reference point is never taken.

    Args:
        point: The (r, z) reference point.
        r: Radial coordinates of the outline.
        z: Height coordinates of the outline.
        axis: The (r, z) of the magnetic axis.
        is_closed: Whether the outline closes on itself.

    Returns:
        Tuple of ((r, z) of the closest point, distance), or (None, inf) if no point
        faces the axis.
    """
    starts = np.column_stack([r, z]).astype(float)
    ends = np.roll(starts, -1, axis=0) if is_closed else starts[1:]
    if not is_closed:
        starts = starts[:-1]
    point = np.asarray(point, float)
    segs = ends - starts
    lens = np.sum(segs**2, axis=1)
    along = np.clip(
        np.sum((point - starts) * segs, axis=1) / np.where(lens > 0, lens, 1), 0, 1
    )
    feet = starts + along[:, None] * segs
    facing = (feet - point) @ (np.asarray(axis, float) - point) >= 0
    if not facing.any():
        return None, float("inf")
    dists = np.where(facing, np.linalg.norm(feet - point, axis=1), np.inf)
    idx = int(np.argmin(dists))
    return (float(feet[idx, 0]), float(feet[idx, 1])), float(dists[idx])


def interpolate_branch(r, z, axis, at, theta_range, along="z"):
    """Interpolate one branch of an outline, selected by its angle about the axis, as
    FEEQS measures the WEST gaps (pchip, in coordinates relative to the axis).

    Args:
        r: Radial coordinates of the outline.
        z: Height coordinates of the outline.
        axis: The (r, z) the angles are taken about, the magnetic axis in FEEQS.
        at: The absolute height (along="z") or radius (along="r") to evaluate at.
        theta_range: (low, high) angles in radians of the points that form the branch.
            A low above high wraps around pi, for the inboard side.
        along: "z" to find the radius at a height, "r" to find the height at a radius.

    Returns:
        The radius (or height) of the branch, or None if it does not reach `at`.
    """
    from scipy.interpolate import PchipInterpolator

    r0, z0 = axis
    d_r, d_z = np.asarray(r, float) - r0, np.asarray(z, float) - z0
    theta = np.arctan2(d_z, d_r)
    low, high = theta_range
    on_branch = (
        (theta > low) & (theta < high) if low < high else (theta > low) | (theta < high)
    )
    x, y = (d_z, d_r) if along == "z" else (d_r, d_z)
    x, y = x[on_branch], y[on_branch]
    x, unique = np.unique(x, return_index=True)
    y = y[unique]
    target = at - (z0 if along == "z" else r0)
    if len(x) < 2 or not x[0] <= target <= x[-1]:
        return None
    return float(PchipInterpolator(x, y)(target)) + (r0 if along == "z" else z0)


def geometric_centre(r, z):
    """The centre of the bounding box of an outline."""
    return (float(np.min(r) + np.max(r)) / 2, float(np.min(z) + np.max(z)) / 2)


def psi_contour(time_slice, level):
    """The contour of the poloidal flux of an equilibrium at a level, from the GGD
    that NICE fills, or else from profiles_2d.

    Args:
        time_slice: The equilibrium time slice.
        level: The flux to contour.

    Returns:
        List of (N, 2) arrays of (r, z), one per piece of the contour.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        if len(time_slice.ggd) > 0 and len(time_slice.ggd[0].psi) > 0:
            ggd = time_slice.ggd[0]
            r, z = ggd.r[0].values, ggd.z[0].values
            contour = ax.tricontour(r, z, ggd.psi[0].values, levels=[level])
        elif len(time_slice.profiles_2d) > 0:
            p2d = time_slice.profiles_2d[0]
            r, z = np.asarray(p2d.grid.dim1), np.asarray(p2d.grid.dim2)
            psi = np.asarray(p2d.psi)
            psi = psi.T if psi.shape == (len(r), len(z)) else psi
            contour = ax.contour(r, z, psi, levels=[level])
        else:
            return []
        return [np.asarray(seg) for seg in contour.allsegs[0] if len(seg) > 1]
    finally:
        plt.close(fig)
