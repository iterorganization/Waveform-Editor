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

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a constant line containing the start and end points will be generated.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = np.array([self.start, self.end])
        values = self.value * np.ones(len(time))
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.value

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.value

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return 0

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return 0

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

        # Update state
        values_changed = self.value != value
        if values_changed:
            self.value = value
        # Ensure watchers are called after both values are updated
        self.param.update(
            values_changed=values_changed,
            start_value_set=self.user_value is not None,
        )
