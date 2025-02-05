from typing import Optional

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
        self.start_derivative = 0.0
        self.end_derivative = 0.0
        super().__init__(**kwargs)

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = self.generate_time()

        self.spline = CubicSpline(
            [self.start, self.end],
            [self.from_, self.to],
            bc_type=((1, self.start_derivative), (1, self.end_derivative)),
        )
        values = self.spline(time)
        return time, values

    def get_derivative(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the derivative values on the provided time array. If no time array is
        provided, a linearly spaced time array will be generated from the start to the
        end of the tendency.
        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = self.generate_time()

        derivative_spline = self.spline.derivative()
        derivatives = derivative_spline(time)
        return time, derivatives

    def generate_time(self) -> np.ndarray:
        """Generates time array containing start and end of the tendency."""
        sampling_rate = 100
        num_steps = int(self.duration * sampling_rate) + 1
        return np.linspace(float(self.start), float(self.end), num_steps)

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

    # Workaround: param doesn't like a @depends on both prev and next tendency
    _trigger = param.Event()

    @depends("prev_tendency.end_value", watch=True)
    def _trigger1(self):
        self._trigger = True

    @depends(
        "next_tendency.start",
        "next_tendency.start_value",
        "next_tendency.start_value_set",
        watch=True,
    )
    def _trigger2(self):
        self._trigger = True

    @depends(
        "_trigger",
        "user_from",
        "user_to",
        watch=True,
        on_init=True,
    )
    def _update_values(self):
        """Updates from/to values."""
        from_ = to = 0.0
        if self.user_from is None:
            if self.prev_tendency is not None:
                _, from_ = self.prev_tendency.get_value(np.array([self.start]))
                from_ = from_[0]
        else:
            from_ = self.user_from
        if self.user_to is None:
            if self.next_tendency is not None and self.next_tendency.start_value_set:
                _, to = self.next_tendency.get_value(np.array([self.end]))
                to = to[0]
        else:
            to = self.user_to

        # Derivatives
        d_start = d_end = 0.0
        if self.prev_tendency is not None:
            _, d_start = self.prev_tendency.get_derivative(np.array([self.start]))
            d_start = d_start[0]
        if self.next_tendency is not None:
            _, d_end = self.next_tendency.get_derivative(np.array([self.end]))
            d_end = d_end[0]

        values_changed = (
            self.from_,
            self.to,
            self.start_derivative,
            self.end_derivative,
        ) != (from_, to, d_start, d_end)

        if values_changed:
            self.from_, self.to = from_, to
            self.start_derivative, self.end_derivative = d_start, d_end

            # Ensure watchers are called after both values are updated
            self.param.update(
                values_changed=values_changed,
                start_value_set=self.user_from is not None,
            )
