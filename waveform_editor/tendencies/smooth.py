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
        super().__init__(**kwargs)

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If no time array is
        provided, a linearly spaced time array will be generated from the start to the
        end of the tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            sampling_rate = 100
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(float(self.start), float(self.end), num_steps)

        values = self.spline(time)

        if np.any(np.isnan(values)):
            raise ValueError(
                "A spline was generated at a time outside of its generated time range."
            )

        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """

        derivative_spline = self.spline.derivative()
        derivatives = derivative_spline(time)
        return derivatives

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
        "start",
        "end",
        watch=True,
        on_init=True,
    )
    def _update_values(self):
        """Updates from/to values."""
        from_ = to = 0.0
        if self.user_from is None:
            if self.prev_tendency is not None:
                from_ = self.prev_tendency.end_value
        else:
            from_ = self.user_from
        if self.user_to is None:
            if self.next_tendency is not None and self.next_tendency.start_value_set:
                to = self.next_tendency.start_value
        else:
            to = self.user_to

        # Derivatives
        d_start = d_end = 0.0
        if self.prev_tendency is not None:
            d_start = self.prev_tendency.end_derivative
        if self.next_tendency is not None:
            d_end = self.next_tendency.start_derivative

        if self.start >= self.end:
            return

        self.spline = CubicSpline(
            [self.start, self.end],
            [from_, to],
            bc_type=((1, d_start), (1, d_end)),
            extrapolate=False,
        )

        values_changed = (
            self.from_,
            self.to,
            self.start_derivative,
            self.end_derivative,
        ) != (from_, to, d_start, d_end)

        if values_changed:
            self.from_, self.to = from_, to

        # Ensure watchers are called after both values are updated
        self.param.update(
            start_derivative=d_start,
            end_derivative=d_end,
            values_changed=values_changed,
            start_value_set=self.user_from is not None,
        )
