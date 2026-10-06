"""The gaps between an ITER plasma and the first wall, as defined in DINA.

The definitions follow DINA-IMAS (src/scenario/g_gaps_rus.f, tools/GUI/captions.py):
- gaps 1 and 2 are the minimum distances from the reference strike points to the
  separatrix, which DINA only measures in the divertor phase, to the divertor legs;
- gaps 4 and 5 are the minimum distances from points on the wall to the boundary,
  towards the magnetic axis;
- Rmin and Rmax are the radii of the innermost and outermost boundary points, measured
  from r=0 at the height of those points.
"""

import math

import numpy as np

from waveform_editor.shape_editor.plasma_shape_calc import (
    Gap,
    closest_outline_point,
    closest_point_facing,
    geometric_centre,
    psi_contour,
)

# Fixed gap measurement points on the wall, in metres (r, z):
GAP_POINTS = {
    "gap1": (4.2230, -3.7920),
    "gap2": (5.5650, -4.4040),
    "gap4": (7.5095, 2.9971),
    "gap5": (5.3315, 4.5804),
}

GAP_METADATA = {
    "gap1": ("g₁", "cm", "Inner divertor leg gap"),
    "gap2": ("g₂", "cm", "Outer divertor leg gap"),
    "gap4": ("g₄", "cm", "Point at 2 o'clock gap"),
    "gap5": ("g₅", "cm", "Uppest boundary point gap"),
    "Rmin": ("Rₘᵢₙ", "m", "Inboard boundary radius"),
    "Rmax": ("Rₘₐₓ", "m", "Outboard boundary radius"),
}


def _distance_to_outline(point, r, z, is_closed=True):
    return closest_outline_point(point, r, z, is_closed=is_closed)[1]


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
        "separatrix_contour": extract_separatrix_from_time_slice(time_slice),
        "magnetic_axis": (float(axis.r), float(axis.z)),
    }


def extract_separatrix_from_time_slice(time_slice):
    """The contour of the boundary flux of an equilibrium, legs included."""
    if time_slice is None:
        return []
    psi_boundary = time_slice.global_quantities.psi_boundary
    if not _is_filled(psi_boundary):
        psi_boundary = time_slice.boundary.psi
    if not _is_filled(psi_boundary):
        return []
    return psi_contour(time_slice, float(psi_boundary))


def _is_filled(value):
    """Whether an IDS float is filled."""
    return value is not None and float(value) != -9e40


def _normalize_contour_segments(separatrix_contour):
    """Normalize contour segment representations into a list of (N, 2) arrays."""
    if separatrix_contour is None:
        return []
    if (
        isinstance(separatrix_contour, (tuple, list))
        and len(separatrix_contour) == 2
        and isinstance(separatrix_contour[0], (list, np.ndarray))
        and len(separatrix_contour[0]) > 0
        and not isinstance(separatrix_contour[0][0], (list, np.ndarray, dict))
    ):
        r, z = (
            np.asarray(separatrix_contour[0], float),
            np.asarray(separatrix_contour[1], float),
        )
        return [np.column_stack([r, z])] if len(r) > 1 else []

    segments = []
    for seg in separatrix_contour:
        arr = (
            np.column_stack([seg["x"], seg["y"]])
            if isinstance(seg, dict) and "x" in seg
            else np.asarray(seg, float)
        )
        if arr.ndim == 2 and arr.shape[1] >= 2 and len(arr) > 1:
            segments.append(arr[:, :2])
    return segments


def _dina_divertor_sign(k, r_target, z_target, r_orig, z_orig, magnetic_axis):
    """Calculate the DINA sign for divertor gaps 1 and 2."""
    if magnetic_axis is None:
        return 1.0
    rmag, zmag = magnetic_axis
    vecpro = (r_target - rmag) * (z_orig - zmag) - (z_target - zmag) * (r_orig - rmag)
    s_vecpro = 1.0 if vecpro >= 0 else -1.0
    p = k - 1.5
    return (p / abs(p)) * s_vecpro


def is_diverted(segments):
    """Whether a separatrix has divertor legs, which leave the domain, so that a piece
    of its contour does not close on itself."""
    return any(np.linalg.norm(seg[0] - seg[-1]) > 1e-3 for seg in segments)


def compute_gaps(outline_r, outline_z, separatrix_contour=None, magnetic_axis=None):
    """The gaps and radial extent of an ITER plasma, in metres.

    Args:
        outline_r: Radial coordinates of the plasma boundary.
        outline_z: Height coordinates of the plasma boundary.
        separatrix_contour: The separatrix with its legs, as pieces of (N, 2) arrays,
            which only a solved equilibrium has. Without legs there are no gaps 1, 2.
        magnetic_axis: The (r, z) of the magnetic axis, the centre of the outline is
            used without one.

    Returns:
        Dict of gap name to distance in metres, None for gaps 1, 2 without legs.
    """
    items = compute_gap_geometry(
        outline_r, outline_z, separatrix_contour, magnetic_axis
    )
    return {item["key"]: item["distance"] for item in items}


def compute_gap_geometry(
    outline_r, outline_z, separatrix_contour=None, magnetic_axis=None
):
    """The gaps of an ITER plasma, as computed in DINA, together with the points they
    are measured between.

    Args:
        outline_r: Radial coordinates of the plasma boundary.
        outline_z: Height coordinates of the plasma boundary.
        separatrix_contour: The separatrix with its legs, as pieces of (N, 2) arrays,
            which only a solved equilibrium has. Without legs there are no gaps 1, 2.
        magnetic_axis: The (r, z) of the magnetic axis, the centre of the outline is
            used without one.

    Returns:
        List of dicts, one per gap.
    """
    if outline_r is None or outline_z is None or len(outline_r) == 0:
        return []
    r, z = np.asarray(outline_r, float), np.asarray(outline_z, float)
    axis = magnetic_axis[:2] if magnetic_axis is not None else geometric_centre(r, z)
    items = []

    def add(key, orig, target, distance, distance_str):
        symbol, _, name = GAP_METADATA[key]
        items.append(
            {
                "key": key,
                "name": name,
                "symbol": symbol,
                "r_orig": float(orig[0]),
                "z_orig": float(orig[1]),
                "r_target": float(target[0]),
                "z_target": float(target[1]),
                "distance": distance,
                "distance_str": distance_str,
            }
        )

    # A closed boundary has no legs, and the distance from a strike point to it would
    # be to the wrong part of the plasma, so the reference point is shown on its own
    segments = _normalize_contour_segments(separatrix_contour)
    diverted = is_diverted(segments)
    for k, key in enumerate(("gap1", "gap2"), start=1):
        point = GAP_POINTS[key]
        best = None
        for seg in segments if diverted else []:
            target, distance = closest_outline_point(
                point, seg[:, 0], seg[:, 1], is_closed=False
            )
            if best is None or distance < best[1]:
                best = target, distance
        if best is None:
            add(key, point, point, None, "— (no divertor legs)")
            continue
        target, distance = best
        distance *= _dina_divertor_sign(k, *target, *point, axis)
        add(key, point, target, distance, f"{distance * 100:+.3g} cm")

    for key in ("gap4", "gap5"):
        point = GAP_POINTS[key]
        target, distance = closest_point_facing(point, r, z, axis)
        if target is not None:
            add(key, point, target, distance, f"{distance * 100:.3g} cm")

    for key, index in (("Rmin", int(np.argmin(r))), ("Rmax", int(np.argmax(r)))):
        extreme = (r[index], z[index])
        add(key, (0.0, z[index]), extreme, float(r[index]), f"{r[index]:.4g} m")

    return items


def _dina_divertor_sign(k, r_target, z_target, r_orig, z_orig, magnetic_axis):
    """The sign DINA gives gaps 1 and 2 (g_gaps_rus.f), from the side of the axis the
    closest point is on."""
    rmag, zmag = magnetic_axis
    vecpro = (r_target - rmag) * (z_orig - zmag) - (z_target - zmag) * (r_orig - rmag)
    s_vecpro = 1.0 if vecpro >= 0 else -1.0
    p = k - 1.5
    return (p / abs(p)) * s_vecpro


def get_default_iter_gaps():
    """Return default Gap definitions for ITER based on DINA coordinates."""
    return [
        Gap("Inner divertor leg (g₁)", 4.2230, -3.7920, math.radians(-65.0), 0.0),
        Gap("Outer divertor leg (g₂)", 5.5650, -4.4040, math.radians(-150.0), 0.0),
        Gap("Point at 2 o'clock (g₄)", 7.5095, 2.9971, math.radians(135.0), 0.228),
        Gap("Uppest boundary point (g₅)", 5.3315, 4.5804, math.radians(90.0), 0.596),
        # Measured from r=0, at the height of the innermost and outermost point
        Gap("Inboard mid-plane (Rmin)", 0.0, 0.7777, 0.0, 4.2099),
        Gap("Outboard mid-plane (Rmax)", 0.0, 0.4665, 0.0, 8.2006),
    ]
