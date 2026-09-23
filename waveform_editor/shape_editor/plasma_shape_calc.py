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


def compute_outline_from_params(
    a, center_r, center_z, kappa, delta, rx, zx, n_desired_bnd_points
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

    # First segment: main plasma shape
    theta1 = math.pi / (nb_point1 - 1)
    asin_delta = math.asin(delta)
    for i in range(nb_point1):
        theta = i * theta1
        r = r0 + a * math.cos(theta + asin_delta * math.sin(theta))
        z = z0 + a * kappa * math.sin(theta)
        points.append((r, z))

    # Second arc: inner divertor leg
    ri = ((rx + r0 - a) / 2.0) + ((z0 - zx) ** 2) / (2.0 * (rx - r0 + a))
    ai = ri - r0 + a
    theta2 = math.asin((z0 - zx) / ai) / (nb_point2 + 1)
    for i in range(nb_point2):
        theta = (i + 1) * theta2
        r = ri - ai * math.cos(theta)
        z = z0 - ai * math.sin(theta)
        points.append((r, z))

    # Third arc: outer divertor leg
    re = ((rx + r0 + a) / 2.0) + ((z0 - zx) ** 2) / (2.0 * (rx - r0 - a))
    ae = r0 + a - re
    theta3 = math.asin((z0 - zx) / ae) / (nb_point3 + 1)
    for i in range(nb_point3):
        theta = (i + 1) * theta3
        r = re + ae * math.cos(theta)
        z = z0 - ae * math.sin(theta)
        points.append((r, z))

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
