import numpy as np
import param
from param import depends
from scipy.interpolate import CubicSpline

from waveform_editor.tendencies.base import BaseTendency


class SmoothTendency(BaseTendency):
    """
    Smooth tendency class for a signal with a cubic spline interpolation.
    """

    from_value = param.Number(
        default=0.0, doc="The value at the start of the smooth tendency."
    )
    user_from_value = param.Number(
        default=0.0,
        doc="The value at the start of the smooth tendency, as provided by the user.",
        allow_None=True,
    )

    to = param.Number(default=1.0, doc="The value at the end of the smooth tendency.")
    user_to = param.Number(
        default=0.0,
        doc="The value at the end of the smooth tendency, as provided by the user.",
        allow_None=True,
    )

    derivative_start = param.Number(
        default=0.0,
        doc="The derivative at the start of the smooth tendency.",
    )
    derivative_end = param.Number(
        default=0.0,
        doc="The derivative at the end of the smooth tendency.",
    )

    def __init__(
        self, *, start=None, duration=None, end=None, from_value=None, to=None
    ):
        super().__init__(start, duration, end)
        self.user_from_value = from_value
        self.user_to = to

        self._update_from_value()
        self._update_to()
        self._get_derivatives()

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            sampling_rate = 100
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(float(self.start), float(self.end), num_steps)

        spline = CubicSpline(
            [self.start, self.end],
            [self.from_value, self.to],
            bc_type=((1, self.derivative_start), (1, self.derivative_end)),
        )
        values = spline(time)
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.from_value

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.to

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.derivative_start

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self.derivative_end

    @depends("prev_tendency", "next_tendency", watch=True)
    def _get_derivatives(self):
        """Looks for the previous and next tendencies, and gets their derivatives at
        the end and start, respectively. If a neighbouring tendency does not exist,
        the default value will be used instead.
        """
        if self.prev_tendency is not None:
            self.derivative_start = self.prev_tendency.get_derivative_end()

        if self.next_tendency is not None:
            self.derivative_end = self.next_tendency.get_derivative_start()

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
    def _update_to(self):
        """Updates to value. If the `to` keyword is given explicitly by the user,
        this value will be used. Otherwise, the first value of the next tendency
        is chosen. If there is no next tendency, it is set to the default value."""
        if self.user_to is None:
            if self.next_tendency is not None:
                self.to = self.next_tendency.get_start_value()
        else:
            self.to = self.user_to
