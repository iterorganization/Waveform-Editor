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
            time = []
            values = []
            eps = 1e-8 * self.duration / self.frequency

            wrapped_phase = self.phase % (2 * np.pi)
            time.append(self.start)
            values.append(self._calc_sawtooth_wave(self.start))

            current_time = (
                self.start
                + self.period / 2
                - (wrapped_phase / (2 * np.pi)) * self.period
            )
            if current_time < self.start:
                current_time += self.period

            time.extend(np.arange(current_time, self.end, self.period))
            time.extend(np.arange(current_time - eps, self.end, self.period))
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
        return self._calc_sawtooth_wave(self.start)

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
