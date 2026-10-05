"""The gaps between an ITER plasma and the first wall, as defined in DINA.

The gap definitions and measurement points are taken from DINA-IMAS:
- gaps 1, 2, 4, 5 are the minimum distances from fixed wall coordinates to the
  plasma boundary outline.
- Rmin and Rmax are the inboard and outboard radial extents (min and max R) of
  the plasma boundary.
"""

import math

import numpy as np

from waveform_editor.shape_editor.plasma_shape_calc import Gap, closest_outline_point

# Fixed gap measurement points on the wall, in metres (r, z):
GAP_POINTS = {
    "gap1": (4.2230, -3.7920),
    "gap2": (5.5650, -4.4040),
    "gap4": (7.5095, 2.9971),
    "gap5": (5.3315, 4.5804),
}

WALL_REFERENCE_POINTS = {
    "Rmin": (4.0599, 0.7777),
    "Rmax": (8.2806, 0.4665),
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


def extract_separatrix_from_time_slice(time_slice):
    """Extract separatrix isocontour segments from an equilibrium time slice."""
    if time_slice is None:
        return []

    b_psi = getattr(
        getattr(time_slice, "global_quantities", None), "psi_boundary", None
    )
    if b_psi is None or float(b_psi) == -9e40:
        b_psi = getattr(getattr(time_slice, "boundary", None), "psi", None)
    if b_psi is None or float(b_psi) == -9e40:
        return []
    b_psi = float(b_psi)

    import matplotlib.pyplot as plt

    def _contour_segs(cs):
        segs = [np.asarray(seg) for seg in cs.allsegs[0] if len(seg) > 1]
        plt.close(fig)
        return segs

    # 1. Try GGD (NICE output)
    if hasattr(time_slice, "ggd") and len(time_slice.ggd) > 0:
        try:
            g = time_slice.ggd[0]
            r, z, psi = g.r[0].values, g.z[0].values, g.psi[0].values
            if r and z and psi:
                fig, ax = plt.subplots()
                segs = _contour_segs(ax.tricontour(r, z, psi, levels=[b_psi]))
                if segs:
                    return segs
        except Exception:
            pass

    # 2. Try profiles_2d (IMAS grid)
    if hasattr(time_slice, "profiles_2d") and len(time_slice.profiles_2d) > 0:
        try:
            p2d = time_slice.profiles_2d[0]
            r, z, psi = (
                np.asarray(p2d.grid.dim1),
                np.asarray(p2d.grid.dim2),
                np.asarray(p2d.psi),
            )
            if len(r) > 0 and len(z) > 0 and psi.size > 0:
                psi_grid = psi.T if psi.shape == (len(r), len(z)) else psi
                fig, ax = plt.subplots()
                segs = _contour_segs(ax.contour(r, z, psi_grid, levels=[b_psi]))
                if segs:
                    return segs
        except Exception:
            pass

    return []


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


def _closest_point_on_segments(point, segments):
    """Find the closest point to `point` across multiple polyline segments."""
    min_dist, best_target = float("inf"), None
    for seg in segments:
        target, dist = closest_outline_point(
            point, seg[:, 0], seg[:, 1], is_closed=False
        )
        if dist < min_dist:
            min_dist, best_target = dist, target
    return best_target, min_dist


def compute_gaps(outline_r, outline_z, separatrix_contour=None, magnetic_axis=None):
    """The gaps and radial extent of an ITER plasma, in metres."""
    if outline_r is None or outline_z is None or len(outline_r) == 0:
        return {}

    r = np.asarray(outline_r, dtype=float)
    z = np.asarray(outline_z, dtype=float)

    gaps = {
        "gap4": closest_outline_point(GAP_POINTS["gap4"], r, z)[1],
        "gap5": closest_outline_point(GAP_POINTS["gap5"], r, z)[1],
        "Rmin": float(np.min(r)),
        "Rmax": float(np.max(r)),
    }

    segments = _normalize_contour_segments(separatrix_contour)
    has_legs = len(segments) > 0 or float(np.min(z)) <= -3.6
    if not segments and has_legs:
        segments = [np.column_stack([r, z])]

    if has_legs:
        for k, name in enumerate(("gap1", "gap2"), start=1):
            pt = GAP_POINTS[name]
            target, dist = _closest_point_on_segments(pt, segments)
            if target is not None:
                sign = _dina_divertor_sign(
                    k, target[0], target[1], pt[0], pt[1], magnetic_axis
                )
                gaps[name] = dist * sign
            else:
                gaps[name] = None
    else:
        gaps["gap1"] = None
        gaps["gap2"] = None

    return gaps


def compute_gap_geometry(
    outline_r, outline_z, separatrix_contour=None, magnetic_axis=None
):
    """Compute measuring points and distance segments for ITER gaps."""
    if outline_r is None or outline_z is None or len(outline_r) == 0:
        return []

    r, z = np.asarray(outline_r, float), np.asarray(outline_z, float)
    items = []

    segments = _normalize_contour_segments(separatrix_contour) or [
        np.column_stack([r, z])
    ]
    for k, name in enumerate(("gap1", "gap2"), start=1):
        r_orig, z_orig = GAP_POINTS[name]
        target, dist = _closest_point_on_segments((r_orig, z_orig), segments)
        if target is not None:
            sign = _dina_divertor_sign(
                k, target[0], target[1], r_orig, z_orig, magnetic_axis
            )
            symbol, _, full_name = GAP_METADATA[name]
            items.append(
                {
                    "name": full_name,
                    "symbol": symbol,
                    "r_orig": r_orig,
                    "z_orig": z_orig,
                    "r_target": target[0],
                    "z_target": target[1],
                    "distance": dist,
                    "distance_str": f"{dist * sign * 100:+.2f} cm",
                }
            )

    ref_points = {**GAP_POINTS, **WALL_REFERENCE_POINTS}
    min_r, max_r = float(np.min(r)), float(np.max(r))
    for name in ("gap4", "gap5", "Rmin", "Rmax"):
        r_orig, z_orig = ref_points[name]
        (r_target, z_target), dist = closest_outline_point((r_orig, z_orig), r, z)
        symbol, _, full_name = GAP_METADATA[name]
        dist_str = (
            f"Rₘᵢₙ = {min_r:.4g} m (gap: {dist * 100:.3g} cm)"
            if name == "Rmin"
            else f"Rₘₐₓ = {max_r:.4g} m (gap: {dist * 100:.3g} cm)"
            if name == "Rmax"
            else f"{dist * 100:.3g} cm"
        )
        items.append(
            {
                "name": full_name,
                "symbol": symbol,
                "r_orig": r_orig,
                "z_orig": z_orig,
                "r_target": r_target,
                "z_target": z_target,
                "distance": dist,
                "distance_str": dist_str,
            }
        )

    return items


def get_default_iter_gaps():
    """Return default Gap definitions for ITER based on DINA coordinates."""
    return [
        Gap("Inner divertor leg (g₁)", 4.2230, -3.7920, math.radians(-115.0), 0.0),
        Gap("Outer divertor leg (g₂)", 5.5650, -4.4040, math.radians(-150.0), 0.0),
        Gap("Point at 2 o'clock (g₄)", 7.5095, 2.9971, math.radians(135.0), 0.228),
        Gap("Uppest boundary point (g₅)", 5.3315, 4.5804, math.radians(90.0), 0.596),
        Gap("Inboard mid-plane (Rmin)", 4.0599, 0.7777, math.radians(0.0), 0.150),
        Gap("Outboard mid-plane (Rmax)", 8.2806, 0.4665, math.radians(180.0), 0.080),
    ]
