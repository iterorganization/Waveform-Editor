"""Pure geometry calculations for the plasma shape, with no Panel dependency."""

import math
from dataclasses import dataclass


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
