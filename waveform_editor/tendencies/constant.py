from typing import Optional

import numpy as np
import param
from param import depends

from waveform_editor.tendencies.base import BaseTendency


class ConstantTendency(BaseTendency):
    """
    Constant tendency class for a constant signal.
    """

    user_value = param.Number(
        default=None,
        doc="The constant value of the tendency provided by the user.",
    )

    def __init__(self, **kwargs):
        self.value = 0.0
        super().__init__(**kwargs)

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If no time array is
        provided, a constant line containing the start and end points will be generated.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = np.array([self.start, self.end])
        values = self.value * np.ones(len(time))
        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        derivatives = np.zeros(len(time))
        return derivatives

    @depends(
        "prev_tendency.end_value",
        "user_value",
        watch=True,
        on_init=True,
    )
    def _calc_values(self):
        """Update the actual value. If the `value` keyword is given explicitly by the
        user, this will be used. Otherwise, if there exists a previous its last value
        will be chosen. If neither one exists, it is set to the default value."""
        value = 0.0  # default
        if self.user_value is None:
            if self.prev_tendency is not None:
                value = self.prev_tendency.end_value
        else:
            value = self.user_value

        # Update state and cast to bool, as param does not like numpy booleans
        values_changed = bool(self.value != value)
        if values_changed:
            self.value = value
        # Ensure watchers are called after both values are updated
        self.param.update(
            values_changed=values_changed,
            start_value_set=self.user_value is not None,
        )
