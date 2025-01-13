import numpy as np
import param
from param import depends

from waveform_editor.tendencies.base import BaseTendency


class PeriodicBaseTendency(BaseTendency):
    """A base class for different periodic tendency types."""

    base = param.Number(default=0.0, doc="The baseline value of the periodic tendency.")
    user_base = param.Number(
        default=0.0,
        doc="The baseline value of the periodic tendency provided by the user.",
        allow_None=True,
    )

    amplitude = param.Number(default=1.0, doc="The amplitude of the periodic tendency.")

    frequency = param.Number(
        default=1.0,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        doc="The frequency of the periodic tendency.",
    )
    user_frequency = param.Number(
        default=1.0,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        doc="The frequency of the periodic tendency, as provided by the user.",
        allow_None=True,
    )

    period = param.Number(
        default=1.0,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        doc="The period of the periodic tendency.",
    )
    user_period = param.Number(
        default=1.0,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        doc="The period of the periodic tendency, as provided by the user.",
        allow_None=True,
    )

    def __init__(
        self,
        *,
        start=None,
        duration=None,
        end=None,
        base=None,
        amplitude=None,
        frequency=None,
        period=None,
    ):
        super().__init__(start, duration, end)
        self.user_base = base
        self.user_frequency = frequency
        self.user_period = period

        self.amplitude = amplitude
        self._update_frequency()
        self._update_base()
        self._update_rate()

    @depends("next_tendency", "prev_tendency", watch=True)
    def _update_base(self):
        """Update the base of the periodic tendency. If the `base` keyword is given
        explicitly by the user, this value is used. Otherwise, if there exists a
        previous or next tendency, its last value will be chosen. If neither exist, it
        is set to the default value."""
        if self.user_base is None:
            if self.prev_tendency is not None:
                self.base = self.prev_tendency.get_end_value()
            elif self.next_tendency is not None:
                self.base = self.next_tendency.get_start_value()
        else:
            self.base = self.user_base

    def _update_frequency(self):
        """Updates the frequency and period of the periodic tendency.

        Args:
            frequency: The frequency of the tendency, provided by the user
            period: The period of the tendency, provided by the user
        """
        if self.user_frequency is not None and self.user_period is not None:
            if not np.isclose(self.user_frequency, 1 / self.user_period):
                raise ValueError(
                    "Both the frequency and the period of a periodic tendency is "
                    "provided, but these do not match (freq != 1 / period)."
                )
            self.frequency = self.user_frequency
            self.period = self.user_period
        elif self.user_frequency is not None:
            self.frequency = self.user_frequency
            self.period = 1 / self.user_frequency
        elif self.user_period is not None:
            self.period = self.user_period
            self.frequency = 1 / self.user_period

    def _update_rate(self):
        """Updates the rate of change for the periodic tendency. This method can be
        overridden by child classes to provide a custom implementation."""
        pass
