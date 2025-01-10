import numpy as np
from param import depends

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SawtoothWaveTendency(PeriodicBaseTendency):
    """A tendency representing a sawtooth wave."""

    def __init__(
        self,
        *,
        start=None,
        duration=None,
        end=None,
        base=None,
        amplitude=None,
        frequency=None,
    ):
        super().__init__(start, duration, end, base, amplitude, frequency)
        self._update_rate()

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
            time = []
            values = []
            period = 1 / self.frequency
            eps = 1e-8 * self.duration / self.frequency

            time.append(self.start)
            values.append(self.base)

            time.extend(np.arange(self.start + period / 2, self.end, period))
            time.extend(np.arange(self.start + period / 2 - eps, self.end, period))
            time.sort()

            for i in range(1, len(time)):
                if i % 2 == 0:
                    values.append(self.base - self.amplitude)
                else:
                    values.append(self.base + self.amplitude)
            if time[-1] != self.end:
                time.append(self.end)
                values.append(self._calc_sawtooth_wave(self.end))
            time = np.array(time)
            values = np.array(values)
        else:
            values = self._calc_sawtooth_wave(time)

        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.base

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

        t = (time - self.start + 0.5 / self.frequency) % (1 / self.frequency)
        sawtooth_wave = (t * self.frequency) * 2 - 1
        return self.base + self.amplitude * sawtooth_wave

    @depends("amplitude", "frequency", watch=True)
    def _update_rate(self):
        """Calculates the rate of change."""
        self.rate = 2 * self.frequency * self.amplitude
