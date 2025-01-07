import numpy as np
import param
from param import depends
from scipy.interpolate import CubicSpline

from waveform_editor.tendencies.base_tendency import BaseTendency


class SmoothTendency(BaseTendency):
    """
    Smooth tendency class for a signal with a cubic spline interpolation.
    """

    from_value = param.Number(
        default=0.0, doc="The starting value of the smooth tendency."
    )
    user_from_value = param.Number(
        default=0.0,
        doc="The starting value of the smooth tendency provided by the user.",
        allow_None=True,
    )

    to_value = param.Number(default=1.0, doc="The ending value of the smooth tendency.")
    user_to_value = param.Number(
        default=0.0,
        doc="The ending value of the smooth tendency provided by the user.",
        allow_None=True,
    )

    derivative_start = param.Number(
        default=0.0,
        doc="The derivative at the start.",
    )
    derivative_end = param.Number(
        default=0.0,
        doc="The derivative at the end.",
    )

    def __init__(self, time_interval, from_value=None, to_value=None):
        super().__init__(time_interval)
        self.user_from_value = from_value
        self.user_to_value = to_value

        self._update_from_value()
        self._update_to_value()
        self._calc_derivatives()

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
            time = np.linspace(float(self.start), float(self.end), num_steps)

        spline = CubicSpline(
            [self.start, self.end],
            [self.from_value, self.to_value],
            bc_type=((1, self.derivative_start), (1, self.derivative_end)),
        )
        values = spline(time)
        return time, values

    @depends("prev_tendency", "next_tendency", watch=True)
    def _calc_derivatives(self):
        if self.prev_tendency is not None:
            self.derivative_start = self.prev_tendency.get_derivative_end()

        if self.next_tendency is not None:
            self.derivative_end = self.next_tendency.get_derivative_start()

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.from_value

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.to_value

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.derivative_start

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self.derivative_end

    @depends("prev_tendency", watch=True)
    def _update_from_value(self):
        """Update from_value. If the `from` keyword is given explicitly by the user,
        this value will be used. Otherwise, the last value of the previous tendency
        is chosen. If there is no previous tendency, it is set to the default value."""
        if self.user_from_value is None:
            if self.prev_tendency is not None:
                self.from_value = self.prev_tendency.get_end_value()
        else:
            self.from_value = self.user_from_value
        print(self.from_value)

    @depends("next_tendency", watch=True)
    def _update_to_value(self):
        """Update to_value. If the `to` keyword is given explicitly by the user,
        this value will be used. Otherwise, the first value of the next tendency
        is chosen. If there is no next tendency, it is set to the default value."""
        if self.user_to_value is None:
            if self.next_tendency is not None:
                self.to_value = self.next_tendency.get_start_value()
        else:
            self.to_value = self.user_to_value
