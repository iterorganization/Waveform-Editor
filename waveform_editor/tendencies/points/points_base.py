import numpy as np
import param

from waveform_editor.annotations import Annotations
from waveform_editor.tendencies.base import BaseTendency


class PointsBaseTendency(BaseTendency):
    """Base class for tendencies defined by parallel ``time`` and ``value`` lists of
    equal length, one value per time point. ``start`` and ``end`` are always derived
    from ``time[0]``/``time[-1]``; ``start``, ``duration``, and ``end`` may not be
    supplied by the user.

    Subclasses provide the shape of the tendency between (and derivative at) those
    points via :meth:`get_value` and :meth:`get_derivative`, and may customize how the
    raw ``value`` list is validated and cast via :meth:`_process_value` (default:
    numeric-only).
    """

    time = param.Array(default=np.array([0, 1, 2]), doc="The time of each point.")
    value = param.Array(default=np.array([0, 1, 2]), doc="The value at each point.")
    allow_zero_duration = True

    #: Name used in "'<param>' is not allowed in a <name> tendency" error messages.
    _tendency_name = "piecewise"

    def __init__(self, user_time=None, user_value=None, **kwargs):
        self.pre_check_annotations = Annotations()
        time, value, value_type = self._validate_time_value(user_time, user_value)
        self._remove_user_time_params(kwargs)
        super().__init__(
            user_start=time[0],
            user_end=time[-1],
            time=time,
            value=value,
            value_type=value_type,
            **kwargs,
        )
        self.annotations.add_annotations(self.pre_check_annotations)

        self.start_value_set = True
        self.param.update(values_changed=True)

    def _validate_time_value(self, time, value):
        """Validates the provided time and value lists.

        Args:
            time: List of time values.
            value: List of values defined on each time point.

        Returns:
            Tuple containing the validated time array, value array, and value type. If
            any errors are encountered during the validation, the self.time, self.value,
            and self.value_type defaults are returned instead.
        """
        if time is None or value is None:
            error_msg = "Both the `time` and `value` arrays must be specified.\n"
            self.pre_check_annotations.add(self.line_number, error_msg)
        elif len(time) != len(value):
            error_msg = (
                "The provided time and value arrays are not of the same length.\n"
            )
            self.pre_check_annotations.add(self.line_number, error_msg)
        elif len(time) < 1:
            error_msg = (
                "The provided time and value arrays should have a length "
                "of at least 1.\n"
            )
            self.pre_check_annotations.add(self.line_number, error_msg)

        try:
            time = np.asarray_chkfinite(time, dtype=float)
            value, value_type = self._process_value(value)
            is_monotonic = np.all(np.diff(time) > 0)
            if not is_monotonic:
                error_msg = "The provided time array is not monotonically increasing.\n"
                self.pre_check_annotations.add(self.line_number, error_msg)
        except Exception as error:
            self.pre_check_annotations.add(self.line_number, str(error))

        # If there are any errors, use the default values instead
        if not self.pre_check_annotations:
            return time, value, value_type
        else:
            return self.time, self.value, self.value_type

    def _process_value(self, value):
        """Validate and cast the user-provided `value` list to the array used
        internally, alongside the resulting value type.

        Args:
            value: List of values defined on each time point.

        Returns:
            Tuple of the cast value array and its value type. Raise to reject the
            value list; the exception message is reported as an annotation. Default:
            numeric-only (float). Override to support other value types.
        """
        return np.asarray_chkfinite(value, dtype=float), float

    def _remove_user_time_params(self, kwargs):
        """Remove user_start, user_duration, and user_end if they are passed as kwargs,
        and add error messages as annotations. These variables are always derived from
        the `time` array.

        Args:
            kwargs: the keyword arguments.
        """
        line_number = kwargs.get("line_number", 0)
        error_msg = f"is not allowed in a {self._tendency_name} tendency\n"
        for key in ["user_start", "user_duration", "user_end"]:
            if key in kwargs:
                kwargs.pop(key)
                self.pre_check_annotations.add(
                    line_number, f"'{key.replace('user_', '')}' {error_msg}"
                )
