import numpy as np

from waveform_editor.tendencies.points.points_base import PointsBaseTendency


class PiecewiseLinearTendency(PointsBaseTendency):
    """
    A tendency representing a piecewise linear function.
    """

    def get_value(
        self, time: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If a time array is
        provided, the values will be linearly interpolated between the piecewise linear
        points.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            return self.time, self.value

        interpolated_values = np.interp(time, self.time, self.value)
        return time, interpolated_values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        if len(self.time) == 1:
            return np.zeros_like(time, dtype=float)

        # Compute piecewise derivatives
        dv = np.diff(self.value)
        dt = np.diff(self.time)
        piecewise_derivatives = dv / dt

        # Assign derivatives based on which interval each time point falls into
        indices = np.searchsorted(self.time, time, side="right") - 1
        indices = np.clip(indices, 0, len(piecewise_derivatives) - 1)

        return piecewise_derivatives[indices]
