"""The poloidal flux of a NICE result."""

from functools import lru_cache

import numpy as np
from matplotlib.figure import Figure
from matplotlib.tri import Triangulation
from scipy.interpolate import griddata


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


def flux_grid(time_slice, resolution):
    """The poloidal flux on the GGD NICE fills, interpolated linearly onto a regular
    grid over the mesh.

    Args:
        time_slice: The equilibrium time slice.
        resolution: The number of grid points along r and along z.

    Returns:
        Tuple of (grid_r, grid_z, psi_grid), with NaN outside the mesh.
    """
    ggd = time_slice.ggd[0]
    r, z = ggd.r[0].values, ggd.z[0].values
    grid_r = np.linspace(r.min(), r.max(), resolution)
    grid_z = np.linspace(z.min(), z.max(), resolution)
    psi_grid = griddata((r, z), ggd.psi[0].values, tuple(np.meshgrid(grid_r, grid_z)))
    return grid_r, grid_z, psi_grid
