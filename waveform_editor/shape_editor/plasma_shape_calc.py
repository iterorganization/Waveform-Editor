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
