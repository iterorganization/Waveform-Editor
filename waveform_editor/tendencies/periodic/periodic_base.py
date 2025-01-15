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
    user_amplitude = param.Number(
        default=1.0,
        doc="The amplitude of the periodic tendency, as provided by the user.",
        allow_None=True,
    )

    phase = param.Number(default=0.0, doc="The phase shift of the periodic tendency.")
    user_phase = param.Number(
        default=0.0,
        doc="The phase shift of the periodic tendency, as provided by the user",
        allow_None=True,
    )

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

    min = param.Number(
        default=-1.0,
        doc="The minimum value of the periodic tendency.",
    )
    user_min = param.Number(
        default=-1.0,
        doc="The minimum value of the periodic tendency, as provided by the user.",
        allow_None=True,
    )

    max = param.Number(
        default=1.0,
        doc="The maximum value of the periodic tendency.",
    )
    user_max = param.Number(
        default=1.0,
        doc="The maximum value of the periodic tendency, as provided by the user.",
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
        phase=None,
        frequency=None,
        period=None,
        min=None,
        max=None,
    ):
        super().__init__(start, duration, end)
        self.user_base = base
        self.user_amplitude = amplitude
        self.user_phase = phase
        self.user_frequency = frequency
        self.user_period = period
        self.user_min = min
        self.user_max = max

        self._update_phase()
        self._update_bounds()
        self._update_frequency()
        self._update_rate()

    def _update_phase(self):
        """Updates the phase for the periodic tendency."""
        if self.user_phase is not None:
            self.phase = self.user_phase % (2 * np.pi)

    @depends("next_tendency", "prev_tendency", watch=True)
    def _update_bounds(self):
        """Calculates the base, amplitude, minimum, and maximum value of the periodic
        tendency. At most two of these may be provided by the user. If less than two are
        provided, the previous tendency is used to determine the value, otherwise the
        default values are used.
        """
        none_count = sum(
            v is None
            for v in [self.user_base, self.user_amplitude, self.user_min, self.user_max]
        )
        if none_count <= 1:
            raise ValueError(
                "The provided inputs of the periodic tendency are overdetermined. "
                "Only provide at most two of the following keywords: "
                "`base`, `amplitude`, `min`, `max`"
            )
        elif none_count == 2:
            self.base, self.amplitude, self.min, self.max = self._find_missing_values()
        elif none_count == 3:
            if self.user_base is None:
                if self.prev_tendency is not None:
                    self.user_base = self.prev_tendency.get_end_value()
                    self.base, self.amplitude, self.min, self.max = (
                        self._find_missing_values()
                    )
                elif self.next_tendency is not None:
                    self.user_base = self.next_tendency.get_start_value()
                    self.base, self.amplitude, self.min, self.max = (
                        self._find_missing_values()
                    )
                self.user_base = None
            else:
                self.base = self.user_base
                self.max = self.base + self.amplitude
                self.min = self.base - self.amplitude

        self._check_validity_bounds()

    def _check_validity_bounds(self):
        """Check validity of the base, minimum, maximum, and amplitude"""
        if any(
            value is None for value in [self.base, self.amplitude, self.min, self.max]
        ):
            raise ValueError(
                "A base, minimum, maximum, or amplitude value of the periodic tendency "
                "is not set."
            )
        if not np.isclose(self.base, (self.min + self.max) / 2):
            raise ValueError(
                "The base, minimum, and maximum values do not match "
                "(base != (min + max) / 2)"
            )
        if not np.isclose(self.amplitude, (self.max - self.min) / 2):
            raise ValueError(
                "The amplitude, minimum, and maximum values do not match "
                "(amplitude != (max - min) / 2)"
            )

    def _find_missing_values(self):
        """Calculates the None values of the user-defined base, minimum, maximum, and
        amplitude, in the case where two of them are none. A matrix system is solved to
        adhere to the following two equations:

        base = (min + max) / 2
        amplitude = (max - min) / 2

        Returns:
            Array containing the base, amplitude, minimum, and maximum values in that
            order.
        """
        amat = [[1, 0, -0.5, -0.5], [0, 1, 0.5, -0.5]]
        bvec = [0, 0]
        if self.user_base is not None:
            amat.append([1, 0, 0, 0])
            bvec.append(self.user_base)
        if self.user_amplitude is not None:
            amat.append([0, 1, 0, 0])
            bvec.append(self.user_amplitude)
        if self.user_min is not None:
            amat.append([0, 0, 1, 0])
            bvec.append(self.user_min)
        if self.user_max is not None:
            amat.append([0, 0, 0, 1])
            bvec.append(self.user_max)

        return np.linalg.solve(amat, bvec)

    def _update_frequency(self):
        """Updates the frequency and period of the periodic tendency.

        Args:
            frequency: The frequency of the tendency, provided by the user
            period: The period of the tendency, provided by the user
        """
        if self.user_frequency is not None and self.user_period is not None:
            self.frequency = self.user_frequency
            self.period = self.user_period
        elif self.user_frequency is not None:
            self.frequency = self.user_frequency
            self.period = 1 / self.user_frequency
        elif self.user_period is not None:
            self.period = self.user_period
            self.frequency = 1 / self.user_period

        if not np.isclose(self.frequency, 1 / self.period):
            raise ValueError(
                "The frequency and period do not match! (freq != 1 / period)."
            )

    def _update_rate(self):
        """Updates the rate of change for the periodic tendency. This method can be
        overridden by child classes to provide a custom implementation."""
        pass
