import numpy as np
import param

from waveform_editor.annotations import Annotations
from waveform_editor.tendencies.base import BaseTendency
from waveform_editor.tendencies.util import merge_value_types, validate_time_array


class StepsTendency(BaseTendency):
    """
    A tendency representing a step function.
    """

    time = param.Array(default=np.array([0.0]), doc="The start times of each step.")
    value = param.Array(
        default=np.array([0.0], dtype=object), doc="The values of each step."
    )

    def __init__(self, user_time=None, user_value=None, **kwargs):
        self.pre_check_annotations = Annotations()
        time, value, value_type = self._validate_time_value(user_time, user_value)

        if "user_start" in kwargs:
            kwargs.pop("user_start")
            line_number = kwargs.get("line_number", 0)
            self.pre_check_annotations.add(
                line_number, "'start' is not allowed in a steps tendency\n"
            )

        # If neither `duration` nor `end` is given, the tendency simply stops at the
        # last time point
        end_given = "user_duration" in kwargs or "user_end" in kwargs
        if not end_given:
            kwargs["user_end"] = time[-1]

        super().__init__(
            user_start=time[0],
            time=time,
            value=value,
            value_type=value_type,
            **kwargs,
        )
        self.annotations.add_annotations(self.pre_check_annotations)

        if end_given and self.end <= self.time[-1]:
            error_msg = (
                "The tendency must end after its last time point. Provide a "
                "`duration` or `end` that is larger than the last point in "
                "`time`.\n"
            )
            self.annotations.add(self.line_number, error_msg)

        self.start_value_set = True
        self.allow_zero_duration = True
        self.param.update(values_changed=True)

    def get_value(
        self, time: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            # Duplicate each time point so that vertical steps are covered
            time = np.repeat(np.append(self.time, self.end), 2)[1:-1]
            value = np.repeat(self.value, 2)
            return time, value

        indices = np.searchsorted(self.time, time, side="right") - 1
        indices = np.clip(indices, 0, len(self.value) - 1)
        return time, self.value[indices]

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        return np.zeros(len(time))

    def _validate_time_value(self, time, value):
        """Validates the provided time and value lists.

        Args:
            time: List of the start times of each step.
            value: List of the values held during each step.

        Returns:
            Tuple containing the validated time array, value array, and value type.
            If any errors are encountered during validation, the self.time,
            self.value, and self.value_type defaults are returned instead.
        """
        time = validate_time_array(
            self.pre_check_annotations, self.line_number, time, value
        )
        if time is None:
            return self.time, self.value, self.value_type

        for element in value:
            if not isinstance(element, (int, float, str)):
                error_msg = (
                    f"Unsupported value type: {type(element).__name__!r}. Values "
                    "must be numbers or strings.\n"
                )
                self.pre_check_annotations.add(self.line_number, error_msg)
                return self.time, self.value, self.value_type

        value_types = {type(element) for element in value}
        value_type = merge_value_types(value_types)
        if value_type is None:
            error_msg = (
                "All values of a steps tendency must have the same type, or be a mix "
                f"of int and float. Found: {sorted(t.__name__ for t in value_types)}\n"
            )
            self.pre_check_annotations.add(self.line_number, error_msg)
            return self.time, self.value, self.value_type

        value_array = np.array(list(value), dtype=object)
        return time, value_array, value_type
