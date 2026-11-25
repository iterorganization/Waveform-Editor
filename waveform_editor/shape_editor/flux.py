"""The poloidal flux of a NICE result."""

from functools import lru_cache

import numpy as np
from matplotlib.figure import Figure
from matplotlib.tri import LinearTriInterpolator, Triangulation


@lru_cache(maxsize=1)
def _triangulation(r, z):
    """The triangulation of the nodes of a mesh, given as bytes, which is the same
    for every result of a machine."""
    return Triangulation(np.frombuffer(r), np.frombuffer(z))


def mesh(grids_ggd):
    """Get the mesh of NICE from a GGD grid.

    Returns:
        Tuple of the (r, z) of the nodes, and the indices of the nodes of each
        triangle.
    """
    objects = grids_ggd[0].grid[0].space[0].objects_per_dimension
    nodes = np.array([node.geometry.value for node in objects[0].object])
    triangles = np.array([triangle.nodes.value for triangle in objects[2].object])
    return nodes, triangles


def has_grid(equilibrium):
    """Whether an equilibrium holds the mesh of NICE"""
    grids = equilibrium.grids_ggd
    return bool(len(grids) and len(grids[0].grid) and len(grids[0].grid[0].space))


def has_flux_map(time_slice):
    """Whether NICE filled the poloidal flux on the GGD of a time slice."""
    ggd = time_slice.ggd[0]
    return bool(ggd.r[0].values and ggd.z[0].values and ggd.psi[0].values)


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


def flux_grid(time_slice, triangles, resolution):
    """The poloidal flux on the GGD NICE fills, interpolated linearly on the triangles
    of its mesh onto a regular grid over the mesh.

    Args:
        time_slice: The equilibrium time slice.
        triangles: The indices of the nodes of each triangle of the mesh, see mesh.
        resolution: The number of grid points along r and along z.

    Returns:
        Tuple of (grid_r, grid_z, psi_grid), with NaN outside the mesh.
    """
    ggd = time_slice.ggd[0]
    r, z = ggd.r[0].values, ggd.z[0].values
    grid_r = np.linspace(r.min(), r.max(), resolution)
    grid_z = np.linspace(z.min(), z.max(), resolution)
    interpolator = LinearTriInterpolator(
        Triangulation(r, z, triangles), ggd.psi[0].values
    )
    psi_grid = interpolator(*np.meshgrid(grid_r, grid_z)).filled(np.nan)
    return grid_r, grid_z, psi_grid
