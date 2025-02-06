from typing import Optional

import numpy as np

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SawtoothWaveTendency(PeriodicBaseTendency):
    """A tendency representing a sawtooth wave."""

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If no time array is
        provided, a time array will be created from the start to the end of the
        tendency, where time points are defined for every peak and trough in the
        tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """

        if time is None:
            time, values = self._calc_minimal_sawtooth_wave()
        else:
            values = self._calc_sawtooth_wave(time)
        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        rate = 2 * self.frequency * self.amplitude
        return rate * np.ones(len(time))

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

    def _calc_minimal_sawtooth_wave(self):
        """Calculates the time points and values which are minimally required to
        represent the sawtooth wave fully.

        Returns:
            Tuple containing the time and the sawtooth wave values
        """
        time = []
        values = []
        eps = 1e-8 * self.duration / self.frequency

        time.append(self.start)
        values.append(self._calc_sawtooth_wave(self.start))

        current_time = (
            self.start + self.period / 2 - self.phase / (2 * np.pi) * self.period
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
        return time, values
