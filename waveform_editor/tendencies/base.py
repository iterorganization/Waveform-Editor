from abc import abstractmethod
from typing import Optional

import numpy as np
import param
from param import depends

from waveform_editor.annotations import Annotations
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

    start = param.Number(default=0.0, doc="The start time of the tendency.")
    duration = param.Number(
        default=1.0,
        bounds=(0.0, None),
        inclusive_bounds=(False, True),
        doc="The duration of the tendency.",
    )
    end = param.Number(default=1.0, doc="The end time of the tendency.")

    start_value_set = param.Boolean(
        default=False,
        doc="""Marks if the value at self.start is determined by user inputs.

        When this is the case, some tendencies (e.g. linear, smooth) can take their end
        values from the start value of this tendency.
        """,
    )
    start_value = param.Number(default=0.0, doc="Value at self.start")
    end_value = param.Number(default=0.0, doc="Value at self.end")

    start_derivative = param.Number(default=0.0, doc="Derivative at self.start")
    end_derivative = param.Number(default=0.0, doc="Derivative at self.end")

    line_number = param.Number(
        default=0, doc="Line number of the tendency in the YAML file"
    )

    is_first_repeated = param.Boolean(
        default=False,
        doc="Whether the tendency is the first tendency within a repeated tendency",
    )
    annotations = param.ClassSelector(class_=Annotations, default=Annotations())

    def __init__(self, **kwargs):
        self.line_number = kwargs.pop("line_number", 0)
        self.is_first_repeated = kwargs.pop("is_first_repeated", False)

        unknown_kwargs = []
        super().__init__()
        with param.parameterized.batch_call_watchers(self):
            for param_name, value in kwargs.items():
                if param_name not in self.param:
                    unknown_kwargs.append(param_name.replace("user_", ""))
                    continue

                if value is None:
                    self.annotations.add(
                        self.line_number,
                        f"The value of {param_name.replace('user_', '')!r} cannot be "
                        "empty.\nIt will be set to its default value.\n",
                        is_warning=True,
                    )
                    continue

                if isinstance(value, (int, float)) and not np.isfinite(value):
                    self.annotations.add(
                        self.line_number,
                        f"The value for {param_name.replace('user_', '')!r} is not a "
                        "valid number.\nIt will be set to its default value.\n",
                        is_warning=True,
                    )
                    continue

                try:
                    setattr(self, param_name, value)
                except Exception as error:
                    self._handle_error(error)

        self._handle_unknown_kwargs(unknown_kwargs)
        self.values_changed = True

    def _handle_error(self, error):
        """Handle exceptions raised by param assignment and add them as annotations.

        Args:
            param_name: The name of the assigned param
            error_msg: The error message raised by param
        """
        error_msg = str(error)
        # Remove the class name and user_ part of the error message
        replace_str = f"{type(self).__name__}.user_"
        cleaned_msg = error_msg.replace(replace_str, "")
        self.annotations.add(
            self.line_number,
            f"{cleaned_msg}\nThis tendency is ignored.\n",
        )

    def _handle_unknown_kwargs(self, unknown_kwargs):
        """Suggest alternative keyword arguments if the keyword argument is unknown.

        Args:
            unknown_kwargs: List of unknown keyword arguments.
        """
        params_list = [
            word.replace("user_", "") for word in self.param if "user_" in word
        ]
        for unknown_kwarg in unknown_kwargs:
            if ":" in unknown_kwarg:
                error_msg = (
                    f"Found ':' in {unknown_kwarg!r}. "
                    "Did you forget a space after the ':'?\n"
                )
                self.annotations.add(self.line_number, error_msg, is_warning=True)
                continue

            suggestion = self.annotations.suggest(unknown_kwarg, params_list)
            error_msg = (
                f"Unknown keyword passed: {unknown_kwarg!r}. {suggestion}"
                "This keyword will be ignored.\n"
            )
            self.annotations.add(self.line_number, error_msg, is_warning=True)

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
        # If the tendency is the first tendency of a repeated tendency, it is linked to
        # the last tendency in the repeated tendency. In this case we can ignore this
        # error.
        if not np.isclose(self.prev_tendency.end, self.start):
            if self.prev_tendency.end > self.start and not self.is_first_repeated:
                error_msg = (
                    f"The end of the previous tendency ({self.prev_tendency.end})\nis "
                    f"later than the start of the current tendency ({self.start}).\n"
                )
                self.annotations.add(self.line_number, error_msg)
            elif self.prev_tendency.end < self.start:
                error_msg = (
                    "Previous tendency ends before the start of the current tendency.\n"
                    "The values inbetween the tendencies will be linearly interpolated."
                    "\n"
                )
                self.annotations.add(self.line_number, error_msg, is_warning=True)

        self.param.trigger("annotations")

    def set_next_tendency(self, next_tendency):
        """Sets the next tendency as a param.

        Args:
            next_tendency: The tendency follows the current tendency.
        """
        self.next_tendency = next_tendency

    @depends("values_changed", watch=True)
    def _calc_start_end_values(self):
        """Calculate the values, as well as the derivatives, at the start and end
        of the tendency.
        """
        new_start_value, new_start_derivative = self._get_value_and_derivative(
            self.start
        )
        new_end_value, new_end_derivative = self._get_value_and_derivative(self.end)

        with param.parameterized.batch_call_watchers(self):
            self.start_value = new_start_value
            self.start_derivative = new_start_derivative
            self.end_value = new_end_value
            self.end_derivative = new_end_derivative

    def _get_value_and_derivative(self, time):
        """Get the value and derivative of the tendency at a given time."""
        _, value_array = self.get_value(np.array([time]))
        derivative_array = self.get_derivative(np.array([time]))
        return value_array[0], derivative_array[0]

    @abstractmethod
    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array."""
        raise NotImplementedError()

    @abstractmethod
    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array."""
        raise NotImplementedError()

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
        except InconsistentInputsError:
            # Set error and make duration = 1:
            error_msg = "Inputs are inconsistent: start + duration != end"
            self.annotations.add(self.line_number, error_msg)
            if self.prev_tendency is None:
                values = (0, 1, 1)
            else:
                values = (self.prev_tendency.end, 1, self.prev_tendency.end + 1)

        # Check if any value has changed
        if (self.start, self.duration, self.end) != values:
            try:
                self.start, self.duration, self.end = values
            except Exception as error:
                self._handle_error(error)
            # Trigger timing event
            self.times_changed = True
