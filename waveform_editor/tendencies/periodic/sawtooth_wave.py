import numpy as np
from param import depends

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SawtoothWaveTendency(PeriodicBaseTendency):
    """A tendency representing a sawtooth wave."""

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
            sampling_rate = 100
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(float(self.start), float(self.end), num_steps)

        values = self._calc_sawtooth_wave(time)
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.base - self.amplitude

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
        phase = self._calc_phase(time)
        sawtooth_wave = np.where(phase % 1 == 0, -1, 2 * (1 - (phase % 1)) - 1)
        return self.base + self.amplitude * sawtooth_wave

    def _calc_phase(self, time):
        """Calculates the phase of the sawtooth wave at a given time point or
        an array of time points.

        Args:
            time: Single time value or numpy array containing time values.

        Returns:
            The phase of the sawtooth wave.
        """
        return self.frequency * (self.start - time)

    @depends("amplitude", "frequency", watch=True)
    def _update_rate(self):
        """Calculates the rate of change."""
        self.rate = 2 * self.frequency * self.amplitude
