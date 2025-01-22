import numpy as np
import param
from param import depends
from scipy.interpolate import CubicSpline

from waveform_editor.tendencies.base import BaseTendency


class SmoothTendency(BaseTendency):
    """
    Smooth tendency class for a signal with a cubic spline interpolation.
    """

    user_from = param.Number(
        default=None,
        doc="The value at the start of the smooth tendency, as provided by the user.",
    )
    user_to = param.Number(
        default=None,
        doc="The value at the end of the smooth tendency, as provided by the user.",
    )

    def __init__(self, **kwargs):
        self.from_ = 0.0
        self.to = 0.0
        self.derivative_start = 0.0
        self.derivative_end = 0.0
        super().__init__(**kwargs)

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
            [self.from_, self.to],
            bc_type=((1, self.derivative_start), (1, self.derivative_end)),
        )
        values = spline(time)
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.from_

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.to

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.derivative_start

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self.derivative_end

    @depends(
        "prev_tendency.values_changed",
        "next_tendency.values_changed",
        watch=True,
        on_init=True,
    )
    def _calc_derivatives(self):
        """Looks for the previous and next tendencies, and gets their derivatives at
        the end and start, respectively. If a neighbouring tendency does not exist,
        the default value will be used instead.
        """
        d_start = d_end = 0.0
        if self.prev_tendency is not None:
            d_start = self.prev_tendency.get_derivative_end()
        if self.next_tendency is not None:
            d_end = self.next_tendency.get_derivative_start()

        if (self.derivative_start, self.derivative_end) != (d_start, d_end):
            self.derivative_start, self.derivative_end = d_start, d_end
            # Trigger values event
            self.values_changed = True

    @depends(
        "prev_tendency.values_changed",
        "next_tendency.values_changed",
        "user_from",
        "user_to",
        watch=True,
        on_init=True,
    )
    def _update_from_to(self):
        """Updates from/to values."""
        from_ = to = 0.0
        if self.user_from is None:
            if self.prev_tendency is not None:
                from_ = self.prev_tendency.get_end_value()
        else:
            from_ = self.user_from
        if self.user_to is None:
            if self.next_tendency is not None:
                to = self.next_tendency.get_start_value()
        else:
            to = self.user_to

        if (self.from_, self.to) != (from_, to):
            self.from_, self.to = from_, to
            # Trigger values event
            self.values_changed = True
