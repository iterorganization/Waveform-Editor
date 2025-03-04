from typing import Optional

import numpy as np
import param
from param import depends

from waveform_editor.tendencies.base import BaseTendency
from waveform_editor.tendencies.util import (
    InconsistentInputsError,
    solve_with_constraints,
)


class LinearTendency(BaseTendency):
    """
    Linear tendency class for a signal with a linear increase or decrease.
    """

    user_from = param.Number(
        default=None,
        doc="The value at the start of the linear tendency, as provided by the user.",
    )
    user_to = param.Number(
        default=None,
        doc="The value at the end of the linear tendency, as provided by the user.",
    )
    user_rate = param.Number(
        default=None,
        doc="The  rate of change of the linear tendency, as provided by the user.",
    )

    def __init__(self, **kwargs):
        self.from_ = 0.0
        self.to = 0.0
        self.rate = 0.0
        super().__init__(**kwargs)

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If no time array is
        provided, a line containing the start and end points will be generated.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = np.array([self.start, self.end])
        normalized_time = (time - self.start) / self.duration
        values = self.from_ + (self.to - self.from_) * normalized_time
        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        derivatives = self.rate * np.ones(len(time))
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
        "times_changed",
        "user_from",
        "user_to",
        "user_rate",
        watch=True,
        on_init=True,
    )
    def _calc_values(self):
        """Determines the from, to and rate values based on the provided user input.
        If values are missing, it will infer the values based on previous or next
        tendencies. If there are none, it will use the default values for that
        param."""
        inputs = [self.user_from, self.user_rate, self.user_to]
        duration = self.duration or 1e-300  # Prevent division by zero
        constraint_matrix = [[1, duration, -1]]  # from + duration * rate - end = 0
        num_inputs = sum(1 for var in inputs if var is not None)

        # Set defaults if problem is under-determined
        if num_inputs < 2 and inputs[0] is None:
            # From value is not provided, set to 0 or previous end value
            if self.prev_tendency is None:
                inputs[0] = 0
            else:
                inputs[0] = self.prev_tendency.end_value
            num_inputs += 1
            start_value_set = False
        else:
            start_value_set = True

        if num_inputs < 2 and inputs[2] is None:
            # To value is not provided, set to from_ or next start value
            if self.next_tendency is not None and self.next_tendency.start_value_set:
                inputs[2] = self.next_tendency.start_value
            else:
                inputs[2] = inputs[0]
            num_inputs += 1

        try:
            values = solve_with_constraints(inputs, constraint_matrix)
        except InconsistentInputsError:
            error_msg = (
                "Inputs are inconsistent: from + duration * rate != to\n"
                "The 'from', 'to', and 'rate' values will be set to 0.\n"
            )
            self.annotations.add(self.line_number, error_msg, is_warning=True)
            values = (0.0, 0.0, 0.0)

        # Update state and cast to bool, as param does not like numpy booleans
        values_changed = bool((self.from_, self.rate, self.to) != values)
        if values_changed:
            self.from_, self.rate, self.to = values
        # Ensure watchers are called after both values are updated
        self.param.update(
            values_changed=values_changed,
            start_value_set=start_value_set,
        )
