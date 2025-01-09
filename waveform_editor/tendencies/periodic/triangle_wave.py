import numpy as np
from param import depends

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class TriangleWaveTendency(PeriodicBaseTendency):
    """A tendency representing a triangle wave."""

    def __init__(self, time_interval, base=None, amplitude=1.0, frequency=1.0):
        super().__init__(time_interval, base, amplitude, frequency)
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
            time.append(self.start)
            if self.frequency != 0:
                # Only generate points for the peaks and troughs of the triangle wave
                period = 1 / self.frequency
                current_time = self.start + 0.25 * period
                while current_time < self.end:
                    time.append(current_time)
                    current_time += 0.5 * period
                    if current_time > self.end:
                        break

            time.append(self.end)
            time = np.array(time)

        values = self._calc_triangle_wave(time)
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.base

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self._calc_triangle_wave(self.end)

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.rate

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        phase = self._calc_phase(self.end)

        # At the transition points (top and bottom), take derivative that follows
        # the direction of the previous segment (rising keeps rising, falling keeps
        # falling).
        is_transition = phase % 1 == 0
        is_rising = (int(phase) % 2) != 0
        if is_transition:
            return -self.rate if is_rising else self.rate
        return self.rate if is_rising else -self.rate

    def _calc_triangle_wave(self, time):
        """Calculates the point of the triangle wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The value of the triangle wave.
        """
        phase = self._calc_phase(time)
        triangle_wave = 2 * np.abs(phase % 2 - 1) - 1
        return self.base + self.amplitude * triangle_wave

    def _calc_phase(self, time):
        """Calculates the phase of the triangle wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The phase of the triangle wave.
        """
        return 2 * self.frequency * (self.start - time) + 0.5

    @depends("amplitude", "frequency", watch=True)
    def _update_rate(self):
        """Calculates the rate of change."""
        self.rate = 4 * self.frequency * self.amplitude
