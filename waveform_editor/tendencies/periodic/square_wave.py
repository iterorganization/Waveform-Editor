import numpy as np

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SquareWaveTendency(PeriodicBaseTendency):
    """A tendency representing a square wave."""

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
        values = self._calc_square_wave(time)
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self._calc_square_wave(self.start)

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self._calc_square_wave(self.end)

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return 0

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return 0

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
