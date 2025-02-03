from abc import abstractmethod
from typing import Optional

import numpy as np
import param
from param import depends

from waveform_editor.tendencies.util import (
    InconsistentInputsError,
    solve_with_constraints,
)


class BaseTendency(param.Parameterized):
    """
    Base class for different types of tendencies.
    """

    prev_tendency = param.ClassSelector(
        class_=param.Parameterized,
        default=None,
        instantiate=False,
        doc="The tendency that precedes the current tendency.",
    )
    next_tendency = param.ClassSelector(
        class_=param.Parameterized,
        default=None,
        instantiate=False,
        doc="The tendency that follows the current tendency.",
    )

    times_changed = param.Event(doc="Event triggered when start/end times have changed")
    values_changed = param.Event(doc="Event triggered when values have changed")

    user_start = param.Number(
        default=None, doc="The start time of the tendency, as provided by the user."
    )
    user_duration = param.Number(
        default=None,
        bounds=(0.0, None),
        inclusive_bounds=(False, True),
        doc="The duration of the tendency, as provided by the user.",
    )
    user_end = param.Number(
        default=None, doc="The end time of the tendency, as provided by the user."
    )

    start_value_set = param.Boolean(
        default=False,
        doc="""Marks if the value at self.start is determined by user inputs.

        When this is the case, some tendencies (e.g. linear, smooth) can take their end
        values from the start value of this tendency.
        """,
    )
    start_value = param.Number(doc="Value at self.start")
    end_value = param.Number(doc="Value at self.end")

    start_derivative = param.Number(doc="Derivative at self.start")
    end_derivative = param.Number(doc="Derivative at self.end")

    time_error = param.ClassSelector(
        class_=Exception,
        default=None,
        doc="Error that occurred when processing user inputs.",
    )
    value_error = param.ClassSelector(
        class_=Exception,
        default=None,
        doc="Error that occurred when processing user inputs.",
    )

    def __init__(self, **kwargs):
        self.start = 0.0
        self.end = 0.0
        self.duration = 0.0
        self.error = None
        super().__init__(**kwargs)

    def __repr__(self):
        # Override __repr__ from parametrized to avoid showing way too many details
        try:
            settings = ", ".join(
                f"{name}={value!r}"
                for name, value in self.param.values().items()
                if name.startswith("user") or name == "name"
            )
        except RuntimeError:
            settings = "..."
        return f"{self.__class__.__name__}({settings})"

    def set_previous_tendency(self, prev_tendency):
        """Sets the previous tendency as a param.

        Args:
            prev_tendency: The tendency precedes the current tendency.
        """
        self.prev_tendency = prev_tendency

    def set_next_tendency(self, next_tendency):
        """Sets the next tendency as a param.

        Args:
            next_tendency: The tendency follows the current tendency.
        """
        self.next_tendency = next_tendency

    @depends("values_changed", watch=True)
    def _calc_start_end_values(self):
        _, self.start_value = self.get_value(np.array([self.start]))
        _, self.start_derivative = self.get_derivative(np.array([self.start]))

        _, self.end_value = self.get_value(np.array([self.end]))
        _, self.end_derivative = self.get_derivative(np.array([self.end]))

    @abstractmethod
    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the values on the provided time array."""
        pass

    @abstractmethod
    def get_derivative(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the derivative values on the provided time array."""
        pass

    @depends(
        "prev_tendency.times_changed",
        "user_start",
        "user_duration",
        "user_end",
        watch=True,
        on_init=True,
    )
    def _calc_times(self):
        """Validates the user-defined start, duration, and end values. If one or more
        are missing, they are calculated based on the given values, or by neighbouring
        tendencies. The calculated start, duration, and end values are stored in their
        respective params.
        """

        inputs = [self.user_start, self.user_duration, self.user_end]
        constraint_matrix = [[1, 1, -1]]  # start + duration - end = 0
        num_inputs = sum(1 for var in inputs if var is not None)

        # Set defaults if problem is under-determined
        if num_inputs < 2 and inputs[0] is None:
            # Start is not provided, set to 0 or previous end time
            if self.prev_tendency is None:
                inputs[0] = 0
            else:
                inputs[0] = self.prev_tendency.end
            num_inputs += 1

        if num_inputs < 2 and inputs[1] is None:
            inputs[1] = 1.0  # default 1 second duration
            num_inputs += 1

        try:
            values = solve_with_constraints(inputs, constraint_matrix)
            self.time_error = None
        except InconsistentInputsError:
            # Set error and make duration = 1:
            self.time_error = ValueError(
                "Inputs are inconsistent: start + duration != end"
            )
            if self.prev_tendency is None:
                values = (0, 1, 1)
            else:
                values = (self.prev_tendency.end, 1, self.prev_tendency.end + 1)

        # Check if any value has changed
        if (self.start, self.duration, self.end) != values:
            self.start, self.duration, self.end = values
            # Trigger timing event
            self.times_changed = True

        if self.duration <= 0:
            self.time_error = ValueError(
                "Tendency end time must be greater than its start time."
            )
