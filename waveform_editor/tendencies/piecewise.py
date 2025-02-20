from typing import Optional

import numpy as np
import param

from waveform_editor.annotations import Annotations
from waveform_editor.tendencies.base import BaseTendency


class PiecewiseLinearTendency(BaseTendency):
    """
    A tendency representing a piecewise linear function.
    """

    time = param.Array(
        default=np.array([0, 1, 2]), doc="The times of the piecewise tendency."
    )
    value = param.Array(
        default=np.array([0, 1, 2]), doc="The values of the piecewise tendency."
    )

    def __init__(self, user_time=None, user_value=None, **kwargs):
        self.pre_check_annotations = Annotations()
        self.line_number = kwargs.get("line_number", 0)
        time, value = self._validate_time_value(user_time, user_value)
        self._remove_user_time_params(kwargs)
        super().__init__(
            user_start=time[0],
            user_end=time[-1],
            time=time,
            value=value,
            **kwargs,
        )
        self.annotations.add_annotations(self.pre_check_annotations)

        self.start_value_set = True
        self.param.update(values_changed=True)

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If a time array is
        provided, the values will be linearly interpolated between the piecewise linear
        points.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            return self.time, self.value

        interpolated_values = np.interp(time, self.time, self.value)
        return time, interpolated_values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """

        # Compute piecewise derivatives
        dv = np.diff(self.value)
        dt = np.diff(self.time)
        piecewise_derivatives = dv / dt

        # Assign derivatives based on which interval each time point falls into
        indices = np.searchsorted(self.time, time, side="right") - 1
        indices = np.clip(indices, 0, len(piecewise_derivatives) - 1)

        return piecewise_derivatives[indices]

    def _validate_time_value(self, time, value):
        """Validates the provided time and value lists.

        Args:
            time: List of time values.
            value: List of values defined on each time step.

        Returns:
            Tuple containing the validated time and value arrays. If any errors are
            encountered during the validation, the self.time and self.value defaults are
            returned instead.
        """
        if time is None or value is None:
            error_msg = "Both the `time` and `value` arrays must be specified.\n"
            self.pre_check_annotations.add(self.line_number, error_msg)
        elif len(time) != len(value):
            error_msg = (
                "The provided time and value arrays are not of the same length.\n"
            )
            self.pre_check_annotations.add(self.line_number, error_msg)
        elif len(time) < 2:
            error_msg = (
                "The provided time and value arrays should have a length "
                "of at least 2.\n"
            )
            self.pre_check_annotations.add(self.line_number, error_msg)

        try:
            time = np.asarray_chkfinite(time, dtype=float)
            value = np.asarray_chkfinite(value, dtype=float)
            is_monotonic = np.all(np.diff(time) > 0)
            if not is_monotonic:
                error_msg = "The provided time array is not monotonically increasing.\n"
                self.pre_check_annotations.add(self.line_number, error_msg)
        except Exception as error:
            self.pre_check_annotations.add(self.line_number, str(error))

        # If there are any errors, use the default values instead
        if not self.pre_check_annotations:
            return time, value
        else:
            return self.time, self.value

    def _remove_user_time_params(self, kwargs):
        """Remove user_start, user_duration, and user_end if they are passed as kwargs,
        and add error messages as annotations. These variables will be set from the
        self.time array.

        Args:
            kwargs: the keyword arguments.
        """
        line_number = kwargs.get("user_line_number", 0)

        error_msg = "is not allowed in a piecewise tendency\n"
        for key in ["user_start", "user_duration", "user_end"]:
            if key in kwargs:
                kwargs.pop(key)
                self.pre_check_annotations.add(
                    line_number, f"'{key.replace('user_', '')}' {error_msg}"
                )
