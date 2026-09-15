import numpy as np
import param

from waveform_editor.tendencies.points.points_base import PointsBaseTendency
from waveform_editor.tendencies.util import merge_value_types


class StepsTendency(PointsBaseTendency):
    """
    A tendency representing a step function.
    """

    time = param.Array(default=np.array([0.0]), doc="The time of each point.")
    value = param.Array(
        default=np.array([0.0], dtype=object), doc="The value at each point."
    )

    def _process_value(self, value):
        """Validate that all values are int/float/str of a single mergeable type.

        Args:
            value: List of the values held during each step.

        Returns:
            Tuple of the value array (dtype=object) and its merged value type.
        """
        for element in value:
            if not isinstance(element, (int, float, str)):
                raise ValueError(
                    f"Unsupported value type: {type(element).__name__!r}. Values "
                    "must be numbers or strings.\n"
                )

        value_types = {type(element) for element in value}
        value_type = merge_value_types(value_types)
        if value_type is None:
            type_names = sorted(t.__name__ for t in value_types)
            raise ValueError(
                "All values of a steps tendency must have the same type, or be a "
                f"mix of int and float. Found: {type_names}\n"
            )

        return np.array(list(value), dtype=object), value_type

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
            time = np.repeat(self.time, 2)[1:]
            value = np.repeat(self.value, 2)[:-1]
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
