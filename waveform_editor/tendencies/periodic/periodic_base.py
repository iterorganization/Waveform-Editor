import numpy as np
import param
from param import depends

from waveform_editor.tendencies.base import BaseTendency
from waveform_editor.tendencies.util import solve_with_constraints


class PeriodicBaseTendency(BaseTendency):
    """A base class for different periodic tendency types."""

    user_base = param.Number(
        default=None,
        doc="The baseline value of the periodic tendency provided by the user.",
    )
    user_amplitude = param.Number(
        default=None,
        doc="The amplitude of the periodic tendency, as provided by the user.",
    )
    user_min = param.Number(
        default=None,
        doc="The minimum value of the periodic tendency, as provided by the user.",
    )
    user_max = param.Number(
        default=None,
        doc="The maximum value of the periodic tendency, as provided by the user.",
    )
    user_phase = param.Number(
        default=None,
        doc="The phase shift of the periodic tendency, as provided by the user",
    )
    user_frequency = param.Number(
        default=None,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        doc="The frequency of the periodic tendency, as provided by the user.",
    )
    user_period = param.Number(
        default=None,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        doc="The period of the periodic tendency, as provided by the user.",
    )

    def __init__(self, **kwargs):
        self.base = 0.0
        self.amplitude = 0.0
        self.frequency = 1.0
        self.period = 1.0
        self.phase = 0.0
        super().__init__(**kwargs)

    @depends(
        "prev_tendency.values_changed",
        "user_base",
        "user_amplitude",
        "user_min",
        "user_max",
        "user_phase",
        "user_frequency",
        "user_period",
        watch=True,
        on_init=True,
    )
    def _calc_values(self):
        """Update all derived values in a single function"""

        # Determine frequency
        frequency = 1.0
        if self.user_frequency is not None:
            if self.user_period is not None and not np.isclose(
                self.user_frequency, 1 / self.user_period
            ):
                error_msg = (
                    "The frequency and period do not match! (freq != 1 / period).\n"
                    "The period will be ignored and only the frequency is used.\n"
                )
                self.annotations.add(self.line_number, error_msg, is_warning=True)
            frequency = self.user_frequency
        elif self.user_period is not None:
            frequency = 1 / self.user_period

        # Determine phase
        phase = 0.0 if self.user_phase is None else self.user_phase % (2 * np.pi)

        # Determine base and amplitude
        inputs = [self.user_base, self.user_amplitude, self.user_min, self.user_max]
        constraint_matrix = [
            [1, 0, -0.5, -0.5],  # base - (min + max)/2 = 0
            [0, 1, 0.5, -0.5],  # amplitude - (max - min)/2 = 0
        ]
        num_inputs = sum(1 for var in inputs if var is not None)
        start_value_set = num_inputs >= 2

        # Set defaults if problem is under-determined
        if num_inputs < 2 and inputs[0] is None:
            # Base is not provided, set to 0 or previous end value
            if self.prev_tendency is None:
                inputs[0] = 0.0
            else:
                inputs[0] = self.prev_tendency.end_value
            num_inputs += 1

        # Set defaults if problem is under-determined
        if num_inputs < 2 and inputs[1] is None:
            # Amplitude is not provided, set to 0
            inputs[1] = 0.0

        if num_inputs > 2:
            error_msg = (
                "Too many inputs: expected two out of {base, amplitude, min and max}.\n"
                "The 'base', 'amplitude', 'min', and 'max' are set to 0.\n"
            )
            self.annotations.add(self.line_number, error_msg, is_warning=True)
            values = (0.0, 0.0, 0.0, 0.0)
        else:
            values = solve_with_constraints(inputs, constraint_matrix)

        # Update state
        values_changed = (
            self.frequency != frequency
            or self.phase != phase
            or (self.base, self.amplitude) != values[:2]
        )
        if values_changed:
            self.frequency = frequency
            self.period = 1.0 / frequency
            self.phase = phase
            self.base, self.amplitude = values[:2]
        # Ensure watchers are called after both values are updated
        self.param.update(
            values_changed=values_changed,
            start_value_set=start_value_set,
        )
