import numpy as np

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SineWaveTendency(PeriodicBaseTendency):
    """A tendency representing a sine wave."""

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            sampling_rate = 100
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(float(self.start), float(self.end), num_steps)
        values = self._calc_sine(time)
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self._calc_sine(self.start)

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self._calc_sine(self.end)

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""

        return self._calc_derivative(self.start)

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self._calc_derivative(self.end)

    def _calc_sine(self, time):
        """Returns the value of the sine wave."""
        return self.base + self.amplitude * np.sin(
            2 * np.pi * self.frequency * (time - self.start) + self.phase
        )

    def _calc_derivative(self, time):
        """Returns the derivative of the sine wave."""
        return (
            self.amplitude
            * 2
            * np.pi
            * self.frequency
            * np.cos(2 * np.pi * self.frequency * (time - self.start) + self.phase)
        )
