"""Pure geometry calculations for the plasma shape, with no Panel dependency."""

import math

import numpy as np
from scipy.optimize import least_squares


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


def resample_outline(r, z, n_points, start=None):
    """Points evenly spaced along a closed outline.

    Args:
        r: Radial coordinates of the outline.
        z: Height coordinates of the outline.
        n_points: The number of points to take.
        start: The (r, z) the points start from, the point of the outline closest
            to it, so that a corner such as the x-point is kept.

    Returns:
        Tuple of (r, z) arrays of the points.
    """
    r, z = np.asarray(r, dtype=float), np.asarray(z, dtype=float)
    if r[0] == r[-1] and z[0] == z[-1]:
        r, z = r[:-1], z[:-1]
    if start is not None:
        first = np.argmin(np.hypot(r - start[0], z - start[1]))
        r, z = np.roll(r, -first), np.roll(z, -first)
    # Along the outline, closed again
    r_closed, z_closed = np.append(r, r[0]), np.append(z, z[0])
    distance = np.concatenate(
        [[0], np.cumsum(np.hypot(np.diff(r_closed), np.diff(z_closed)))]
    )
    targets = np.linspace(0, distance[-1], n_points, endpoint=False)
    return np.interp(targets, distance, r_closed), np.interp(
        targets, distance, z_closed
    )


def fit_shape_params(params, ranges, misfit):
    """The parameters that bring misfit closest to zero. Of the parameters that do,
    it is those closest to params, so that the shape changes no more than needed.

    Args:
        params: The arguments of compute_outline_from_params to start from.
        ranges: The (min, max) each parameter to fit stays within, by name.
        misfit: Function of the arguments of compute_outline_from_params, returning
            the misfits to bring to zero.

    Returns:
        The arguments of compute_outline_from_params of the fitted shape.
    """
    names = list(ranges)
    low, high = np.array(list(ranges.values()), dtype=float).T
    start = np.clip([params[name] for name in names], low, high)
    scale = high - low

    def residuals(x):
        fitted = {**params, **dict(zip(names, x, strict=True))}
        return np.concatenate([misfit(fitted), 1e-2 * (x - start) / scale])

    result = least_squares(residuals, start, bounds=(low, high), x_scale=scale)
    return {**params, **dict(zip(names, result.x, strict=True))}


def outline_distances(r, z, outline_r, outline_z):
    """The distance of each point to a closed outline.

    Args:
        r: Radial coordinates of the points.
        z: Height coordinates of the points.
        outline_r: Radial coordinates of the outline.
        outline_z: Height coordinates of the outline.
    """
    points = np.column_stack([r, z])
    start = np.column_stack([outline_r, outline_z])
    segment = np.roll(start, -1, axis=0) - start
    length2 = np.maximum((segment**2).sum(axis=1), 1e-30)
    along = ((points[:, None] - start[None]) * segment[None]).sum(axis=2) / length2
    closest = start[None] + np.clip(along, 0, 1)[..., None] * segment[None]
    return np.linalg.norm(points[:, None] - closest, axis=2).min(axis=1)


def fit_params_to_outline(params, outline_r, outline_z, x_point=None):
    """The single null parameters whose shape comes closest to an outline, with the
    x-point kept in place.

    Args:
        params: The arguments of compute_outline_from_params, for the number of
            boundary points.
        outline_r: Radial coordinates of the outline.
        outline_z: Height coordinates of the outline.
        x_point: The (r, z) of the x-point, the lowest point of the outline without.

    Returns:
        The fitted arguments of compute_outline_from_params, and the distances
        between the two outlines [m].
    """
    r, z = np.asarray(outline_r, dtype=float), np.asarray(outline_z, dtype=float)
    r_min, r_max, z_min, z_max = r.min(), r.max(), z.min(), z.max()
    a = (r_max - r_min) / 2
    center_r = (r_max + r_min) / 2
    center_z = z[r.argmax()]
    top = z.argmax()
    if x_point is None:
        x_point = (r[z.argmin()], z_min)
    start = {
        **params,
        "a": a,
        "center_r": center_r,
        "center_z": center_z,
        "kappa": max((z_max - center_z) / a, 0.1),
        "delta": float(np.clip((center_r - r[top]) / a, -0.9, 0.9)),
        "rx": x_point[0],
        "zx": x_point[1],
        "rx_upper": None,
        "zx_upper": None,
    }
    ranges = {
        "a": (0.5 * a, 1.5 * a),
        "center_r": (r_min, r_max),
        "center_z": (z_min, z_max),
        "kappa": (0.1, 3),
        "delta": (-0.95, 0.95),
    }

    def misfit(fitted):
        fit_r, fit_z = compute_outline_from_params(**fitted)
        return np.concatenate(
            [
                outline_distances(r, z, fit_r, fit_z),
                outline_distances(fit_r, fit_z, r, z),
            ]
        )

    fitted = fit_shape_params(start, ranges, misfit)
    return fitted, misfit(fitted)
