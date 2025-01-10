import numpy as np

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SineWaveTendency(PeriodicBaseTendency):
    """A tendency representing a sine wave."""

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
        values = self.base + self.amplitude * np.sin(
            2 * np.pi * self.frequency * (time - time[0])
        )
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.base

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.base + self.amplitude * np.sin(
            2 * np.pi * self.frequency * (self.end - self.start)
        )

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""

        return self.amplitude * 2 * np.pi * self.frequency

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return (
            self.amplitude
            * 2
            * np.pi
            * self.frequency
            * np.cos(2 * np.pi * self.frequency * (self.end - self.start))
        )
