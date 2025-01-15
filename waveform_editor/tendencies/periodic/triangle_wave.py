import numpy as np
from param import depends

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class TriangleWaveTendency(PeriodicBaseTendency):
    """A tendency representing a triangle wave."""

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
            time = self._calc_minimal_triangle_wave()
        values = self._calc_triangle_wave(time)
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self._calc_triangle_wave(self.start)

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self._calc_triangle_wave(self.end)

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self._calc_triangle_derivative(self.start)

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self._calc_triangle_derivative(self.end)

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

    def _calc_triangle_derivative(self, time):
        """Calculates the derivative of the triangle wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The derivative of the triangle wave.
        """
        is_rising = self._calc_phase(time) % (2 * np.pi) > np.pi

        return self.rate if is_rising else -self.rate

    def _calc_phase(self, time):
        """Calculates the phase of the triangle wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The phase of the triangle wave.
        """
        return 2 * np.pi * self.frequency * (time - self.start) + self.phase - np.pi / 2

    @depends("amplitude", "frequency", watch=True)
    def _update_rate(self):
        """Calculates the rate of change."""
        self.rate = 4 * self.frequency * self.amplitude

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
