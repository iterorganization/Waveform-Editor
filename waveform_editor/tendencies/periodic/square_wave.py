from typing import Optional

import numpy as np

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SquareWaveTendency(PeriodicBaseTendency):
    """A tendency representing a square wave."""

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
            time, values = self._calc_minimal_square_wave()
        else:
            values = self._calc_square_wave(time)
        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        return np.zeros(len(time))

    def _calc_square_wave(self, time):
        """Calculates the point of the square wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The value of the square wave.
        """
        t = (time - self.start + self.phase / (2 * np.pi) * self.period) % self.period
        square_wave = np.where(t < (1 / (2 * self.frequency)), 1, -1)
        return self.base + self.amplitude * square_wave

    def _calc_minimal_square_wave(self):
        """Calculates the time points and values which are minimally required to
        represent the square wave fully.

        Returns:
            Tuple containing the time and the square wave values
        """
        time = []
        eps = 1e-8 * self.duration / self.frequency

        time.append(self.start)

        current_time = (
            self.start + self.period / 2 - self.phase / (2 * np.pi) * self.period
        )
        while current_time < self.start:
            current_time += self.period / 2

        time.extend(np.arange(current_time, self.end, self.period / 2))
        time.extend(np.arange(current_time - eps, self.end, self.period / 2))
        time.sort()

        values = [0] * len(time)
        for i in range(len(time)):
            if self.phase < np.pi:
                if i % 4 in {0, 1}:
                    values[i] = self.base + self.amplitude
                elif i % 4 in {2, 3}:
                    values[i] = self.base - self.amplitude
            else:
                if i % 4 in {0, 1}:
                    values[i] = self.base - self.amplitude
                elif i % 4 in {2, 3}:
                    values[i] = self.base + self.amplitude

        if time[-1] != self.end:
            time.append(self.end)
            values.append(self._calc_square_wave(self.end))
        time = np.array(time)
        values = np.array(values)
        return time, values
