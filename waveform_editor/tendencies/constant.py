import numpy as np
import param
from param import depends

from waveform_editor.tendencies.base_tendency import BaseTendency


class ConstantTendency(BaseTendency):
    """
    Constant tendency class for a constant signal.
    """

    value = param.Number(default=0.0, doc="The constant value of the tendency.")
    user_value = param.Number(
        default=0.0,
        doc="The constant value of the tendency provided by the user.",
        allow_None=True,
    )

    def __init__(self, time_interval, value=None):
        super().__init__(time_interval)
        self.user_value = value

    def generate(self, time=None, sampling_rate=100):
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency, with the given sampling rate.

        Args:
            time: The time array on which to generate points.
            sampling_rate: The sampling rate of the generated time array, if no custom
            time array is given.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(self.start, self.end, num_steps)
        values = self.value * np.ones(len(time))
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.value

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.value

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return 0

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return 0

    @depends("next_tendency", "prev_tendency", watch=True)
    def _update_value(self):
        """Update the constant value. If the `value` keyword is given explicitly by the
        user, this value will be used. Otherwise, if there exists a previous or next
        tendency, its last value will be chosen. If neither exist, it is set to the
        default value."""
        if self.user_value is None:
            if self.prev_tendency is not None:
                self.value = self.prev_tendency.get_end_value()
            elif self.next_tendency is not None:
                self.value = self.next_tendency.get_start_value()
        else:
            self.value = self.user_value
