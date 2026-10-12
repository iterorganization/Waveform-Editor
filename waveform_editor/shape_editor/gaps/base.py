"""What all machines' gaps have in common."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from waveform_editor.shape_editor.plasma_shape_calc import compute_outline_from_params


@dataclass
class MeasuredGap:
    """A gap as measured on a plasma boundary."""

    key: str  # The name of the gap, in the GAP_METADATA of its machine
    orig: tuple  # The (r, z) it is measured from
    target: tuple  # The (r, z) it is measured to
    distance: float | None  # In metres, None if it could not be measured


class MachineGaps(ABC):
    """The gaps between a plasma and the machine around it, as one machine defines
    them."""

    # (symbol, unit, full name) of each gap, by name
    GAP_METADATA = {}
    # The gaps the plasmas of the machine are designed with, in metres by name
    DEFAULT_GAPS = {}

    @abstractmethod
    def gap_inputs(self, time_slice):
        """The arguments of measure for a solved equilibrium.

        Args:
            time_slice: The equilibrium time slice.
        """

    def shape_inputs(self, x_points):
        """The arguments of measure besides the outline, for a target shape.

        Args:
            x_points: The (r, z) of each x-point of the shape.
        """
        return {}

    @abstractmethod
    def measure(self, outline_r, outline_z, *args, **kwargs):
        """The MeasuredGap of each gap of a plasma boundary."""

    def compute_gaps(self, *args, **kwargs):
        """The gaps in metres by name, None for those that could not be measured.
        Takes the arguments of measure."""
        return {gap.key: gap.distance for gap in self.measure(*args, **kwargs)}

    def fit_shape(self, params, targets, ranges):
        """The parameters of the parameterized shape whose gaps come closest to the
        targets. Of the shapes that reach them, it is the one closest to params.

        Args:
            params: The arguments of compute_outline_from_params to start from.
            targets: The gap to reach in metres, by name.
            ranges: The (min, max) each parameter to fit stays within, by name.

        Returns:
            The arguments of compute_outline_from_params of the fitted shape.
        """
        names = list(ranges)
        low, high = np.array(list(ranges.values())).T
        start = np.clip([params[name] for name in names], low, high)
        scale = high - low

        def residuals(x):
            fitted = {**params, **dict(zip(names, x, strict=True))}
            r, z = compute_outline_from_params(**fitted)
            x_points = [(fitted["rx"], fitted["zx"])]
            gaps = self.compute_gaps(r, z, **self.shape_inputs(x_points))
            # A gap the shape can no longer be measured on counts as a metre off
            misfit = [
                1.0 if gaps.get(key) is None else gaps[key] - target
                for key, target in targets.items()
            ]
            return np.concatenate([misfit, 1e-2 * (x - start) / scale])

        result = least_squares(residuals, start, bounds=(low, high), x_scale=scale)
        return {**params, **dict(zip(names, result.x, strict=True))}
