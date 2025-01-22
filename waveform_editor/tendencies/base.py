from abc import abstractmethod

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

    @abstractmethod
    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        pass

    @abstractmethod
    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        pass

    @abstractmethod
    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        pass

    @abstractmethod
    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        pass

    @abstractmethod
    def generate(self, time) -> tuple[np.ndarray, np.ndarray]:
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
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
            self.time_error = ValueError(
                "Inputs are inconsistent: start + duration != end"
            )
            values = (
                0 if self.prev_tendency is None else self.prev_tendency.end,
                1,
                self.start + self.duration,
            )

        # Check if any value has changed
        if (self.start, self.duration, self.end) != values:
            self.start, self.duration, self.end = values
            # Trigger timing event
            self.times_changed = True
