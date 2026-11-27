"""The poloidal flux of a NICE result."""

from functools import cached_property, lru_cache

import numpy as np
from matplotlib.figure import Figure
from matplotlib.tri import LinearTriInterpolator, Triangulation


@lru_cache(maxsize=1)
def _triangulation(r, z):
    """The triangulation of the nodes of a mesh, given as bytes, which is the same
    for every result of a machine."""
    return Triangulation(np.frombuffer(r), np.frombuffer(z))


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


class NiceMesh:
    """The triangular mesh NICE solves on, read from the GGD grid of a result."""

    def __init__(self, grids_ggd):
        objects = grids_ggd[0].grid[0].space[0].objects_per_dimension
        self.nodes = np.array([node.geometry.value for node in objects[0].object])
        self.triangles = np.array([tri.nodes.value for tri in objects[2].object])

    @cached_property
    def segments(self):
        """The (r0, z0, r1, z1) of each edge of the triangles, to draw the mesh."""
        r, z = self.nodes[:, 0], self.nodes[:, 1]
        edges = Triangulation(r, z, self.triangles).edges
        return np.hstack([self.nodes[edges[:, 0]], self.nodes[edges[:, 1]]])

    def flux_grid(self, time_slice, resolution):
        """The poloidal flux on the GGD NICE fills, interpolated linearly on the
        triangles of the mesh onto a regular grid over it.

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
        interpolator = LinearTriInterpolator(
            Triangulation(r, z, self.triangles), ggd.psi[0].values
        )
        psi_grid = interpolator(*np.meshgrid(grid_r, grid_z)).filled(np.nan)
        return grid_r, grid_z, psi_grid
