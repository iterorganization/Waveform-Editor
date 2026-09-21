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


def compute_cross_points(center_r, center_z, rotation, length, n_points):
    """Compute a cross-shaped pattern of points, e.g. for constraining the
    plasma boundary tightly near the X-point.

    Args:
        center_r: Major radius of the cross centre.
        center_z: Height of the cross centre.
        rotation: Rotation of the cross, in degrees.
        length: Half-length of each arm, i.e. the distance from the centre
            to each arm's tip, in metres.
        n_points: Total number of points, spread evenly over the 4 arms.

    Returns:
        Tuple of (r, z) coordinate lists.
    """
    if n_points < 4:
        raise ValueError("n_points must be at least 4 to form a cross")

    theta = math.radians(rotation)
    arm1 = (math.cos(theta), math.sin(theta))
    arm2 = (-math.sin(theta), math.cos(theta))
    directions = [arm1, (-arm1[0], -arm1[1]), arm2, (-arm2[0], -arm2[1])]

    base_per_arm, remainder = divmod(n_points, 4)
    points = []
    for i, (dr, dz) in enumerate(directions):
        n_this_arm = base_per_arm + (1 if i < remainder else 0)
        for j in range(n_this_arm):
            dist = (j + 1) / n_this_arm * length
            points.append((center_r + dist * dr, center_z + dist * dz))

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
