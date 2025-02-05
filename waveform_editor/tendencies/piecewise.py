from typing import Optional

import numpy as np
import param

from waveform_editor.tendencies.base import BaseTendency


class PiecewiseLinearTendency(BaseTendency):
    """
    A tendency representing a piecewise linear function.
    """

    time = param.Array(
        default=np.array([0, 1]), doc="The times of the piecewise tendency."
    )
    value = param.Array(
        default=np.array([0, 1]), doc="The values of the piecewise tendency."
    )

    def __init__(self, *, user_time=None, user_value=None):
        self._validate_time_value(user_time, user_value)
        super().__init__(user_start=user_time[0], user_end=user_time[-1])
        self.time = np.array(user_time)
        self.value = np.array(user_value)
        self.start_value_set = True

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate time and values based on the tendency. If a time array is provided,
        the values will be linearly interpolated between the piecewise linear points.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = self.generate_time()

        if np.any(time < self.time[0]) or np.any(time > self.time[-1]):
            raise ValueError(
                f"The provided time array contains values outside the valid range "
                f"({self.time[0]}, {self.time[-1]})."
            )

        interpolated_values = np.interp(time, self.time, self.value)
        return time, interpolated_values

    def get_derivative(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        if time is None:
            time = self.generate_time()

        if np.any(time < self.time[0]) or np.any(time > self.time[-1]):
            raise ValueError(
                f"The provided time array contains values outside the valid range "
                f"({self.time[0]}, {self.time[-1]})."
            )

        derivatives = np.zeros_like(time)

        for i, t in enumerate(time):
            # Find the segment for this particular time
            if t == self.time[-1]:
                derivatives[i] = (self.value[-1] - self.value[-2]) / (
                    self.time[-1] - self.time[-2]
                )
            else:
                # Find the two indices surrounding the time point (t)
                index = np.searchsorted(self.time, t)
                dv = self.value[index + 1] - self.value[index]
                dt = self.time[index + 1] - self.time[index]
                derivatives[i] = dv / dt

        return time, derivatives

    def generate_time(self) -> np.ndarray:
        """Generates time array containing start and end of the tendency."""
        return self.time

    def _validate_time_value(self, time, value):
        """Validates the provided time and value lists.

        Args:
            time: List of time values.
            value: List of values defined on each time step.
        """
        if time is None or value is None:
            raise ValueError("Both the `time` and `value` arrays must be specified.")

        is_monotonic = np.all(np.diff(time) > 0)
        if not is_monotonic:
            raise ValueError("The provided time array is not monotonically increasing.")

        if len(time) != len(value):
            raise ValueError(
                "The provided time and value arrays are not of the same length."
            )

        if len(time) < 2:
            raise ValueError(
                "The provided time and value arrays should have a length of at least 2."
            )
