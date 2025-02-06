from typing import Optional

import numpy as np

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class TriangleWaveTendency(PeriodicBaseTendency):
    """A tendency representing a triangle wave."""

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
            time = self._calc_minimal_triangle_wave()
        values = self._calc_triangle_wave(time)
        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        is_rising = self._calc_phase(time) % (2 * np.pi) > np.pi
        rate = 4 * self.frequency * self.amplitude
        return np.where(is_rising, rate, -rate)

    def _calc_triangle_wave(self, time):
        """Calculates the point of the triangle wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The value of the triangle wave.
        """
        triangle_wave = 2 * np.abs((self._calc_phase(time) / np.pi) % 2 - 1) - 1
        return self.base + self.amplitude * triangle_wave

    def _calc_phase(self, time):
        """Calculates the phase of the triangle wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The phase of the triangle wave.
        """
        return 2 * np.pi * self.frequency * (time - self.start) + self.phase - np.pi / 2

    def _calc_minimal_triangle_wave(self):
        """Calculates the time points at which the peaks and troughs of the triangle
        wave occur, which are minimally required to represent the triangle wave fully.

        Returns:
            Time array for the triangle wave
        """
        time = []
        time.append(self.start)
        # Only generate points for the peaks and troughs of the triangle wave
        current_time = (
            self.start + 0.25 * self.period - self.phase * self.period / (2 * np.pi)
        )
        while current_time < self.end:
            if current_time > self.start:
                time.append(current_time)
            current_time += 0.5 * self.period
        if time[-1] != self.end:
            time.append(self.end)
        time = np.array(time)
        return time
