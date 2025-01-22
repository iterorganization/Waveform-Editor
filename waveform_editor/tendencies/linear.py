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
        values = np.linspace(self.from_, self.to, len(time))
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.from_

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.to

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.rate

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self.rate

    @depends(
        "prev_tendency.values_changed",
        "next_tendency.values_changed",
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
        constraint_matrix = [[1, self.duration, -1]]  # from + duration * rate - end = 0
        num_inputs = sum(1 for var in inputs if var is not None)

        # Set defaults if problem is under-determined
        if num_inputs < 2 and inputs[0] is None:
            # From value is not provided, set to 0 or previous end value
            if self.prev_tendency is None:
                inputs[0] = 0
            else:
                inputs[0] = self.prev_tendency.get_end_value()
            num_inputs += 1

        if num_inputs < 2 and inputs[2] is None:
            # To value is not provided, set to start or next start value
            if self.next_tendency is None:
                inputs[2] = inputs[0]
            else:
                inputs[2] = self.next_tendency.get_start_value()
            num_inputs += 1

        try:
            values = solve_with_constraints(inputs, constraint_matrix)
            self.value_error = None
        except InconsistentInputsError:
            self.value_error = ValueError(
                "Inputs are inconsistent: from + duration * rate != end"
            )
            values = (0.0, 0.0, 0.0)

        if (self.from_, self.rate, self.to) != values:
            self.from_, self.rate, self.to = values
            # Trigger values event
            self.values_changed = True
