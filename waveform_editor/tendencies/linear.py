import numpy as np
import param
from param import depends

from waveform_editor.tendencies.base import BaseTendency


class LinearTendency(BaseTendency):
    """
    Linear tendency class for a signal with a linear increase or decrease.
    """

    from_value = param.Number(
        default=0.0,
        doc="The calculated value at the start of the linear tendency.",
    )
    user_from_value = param.Number(
        default=0.0,
        doc="The value at the start of the linear tendency, as provided by the user.",
        allow_None=True,
    )

    to_value = param.Number(
        default=1.0,
        doc="The calculated value at the end of the linear tendency.",
    )
    user_to_value = param.Number(
        default=1.0,
        doc="The value at the end of the linear tendency, as provided by the user.",
        allow_None=True,
    )

    def __init__(self, time_interval, from_value=None, to_value=None):
        super().__init__(time_interval)
        self.user_from_value = from_value
        self.user_to_value = to_value

        self._update_from_value()
        self._update_to_value()
        self._update_rate()

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a line containing the start and end points will be generated.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = np.array([self.start, self.end])
        values = np.linspace(self.from_value, self.to_value, len(time))
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.from_value

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.to_value

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.rate

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self.rate

    @depends("prev_tendency", watch=True)
    def _update_from_value(self):
        """Updates from_value. If the `from` keyword is given explicitly by the user,
        this value will be used. Otherwise, the last value of the previous tendency
        is chosen. If there is no previous tendency, it is set to the default value."""
        if self.user_from_value is None:
            if self.prev_tendency is not None:
                self.from_value = self.prev_tendency.get_end_value()
        else:
            self.from_value = self.user_from_value

    @depends("next_tendency", watch=True)
    def _update_to_value(self):
        """Updates to_value. If the `to` keyword is given explicitly by the user,
        this value will be used. Otherwise, the first value of the next tendency
        is chosen. If there is no next tendency, it is set to the default value."""
        if self.user_to_value is None:
            if self.next_tendency is not None:
                self.to_value = self.next_tendency.get_start_value()
        else:
            self.to_value = self.user_to_value

    @depends("from_value", "to_value", "start", "end", watch=True)
    def _update_rate(self):
        """Calculate the rate of change."""
        if self.start == self.end:
            self.rate = None
        else:
            self.rate = (self.to_value - self.from_value) / (self.end - self.start)
