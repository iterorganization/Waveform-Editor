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

    def __init__(self, *, time=None, value=None):
        self._validate_time_value(time, value)
        super().__init__(time[0], None, time[-1])
        self.time = np.array(time)
        self.value = np.array(value)

    def generate(self, time=None):
        """Generate time and values based on the tendency. If a time array is provided,
        the values will be linearly interpolated between the piecewise linear points.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            return self.time, self.value

        if np.any(time < self.time[0]) or np.any(time > self.time[-1]):
            raise ValueError(
                f"The provided time array contains values outside the valid range "
                f"({self.time[0]}, {self.time[-1]})."
            )

        interpolated_values = np.interp(time, self.time, self.value)
        return time, interpolated_values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.value[0]

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.value[-1]

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return (self.value[1] - self.value[0]) / (self.time[1] - self.time[0])

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return (self.value[-2] - self.value[-1]) / (self.time[-2] - self.time[-1])

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
