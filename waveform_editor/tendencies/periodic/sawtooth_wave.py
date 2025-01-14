import numpy as np
from param import depends

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SawtoothWaveTendency(PeriodicBaseTendency):
    """A tendency representing a sawtooth wave."""

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a time array will be created from the start to the end of the tendency, where
        time points are defined for every peak and trough in the tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """

        if time is None:
            # TODO: This can be rewritten to only define times at the peaks and troughs
            time = np.linspace(self.start, self.end, 100)
        values = self._calc_sawtooth_wave(time)
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self._calc_sawtooth_wave(self.base)

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self._calc_sawtooth_wave(self.end)

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.rate

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self.rate

    def _calc_sawtooth_wave(self, time):
        """Calculates the point of the sawtooth wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The value of the sawtooth wave.
        """

        t = (
            time
            - self.start
            + 0.5 * self.period
            + self.phase / (2 * np.pi) * self.period
        ) % self.period
        sawtooth_wave = (t * self.frequency) * 2 - 1
        return self.base + self.amplitude * sawtooth_wave

    @depends("amplitude", "frequency", watch=True)
    def _update_rate(self):
        """Calculates the rate of change."""
        self.rate = 2 * self.frequency * self.amplitude
