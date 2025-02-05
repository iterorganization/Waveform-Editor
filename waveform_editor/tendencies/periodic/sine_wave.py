from typing import Optional

import numpy as np

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SineWaveTendency(PeriodicBaseTendency):
    """A tendency representing a sine wave."""

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = self.generate_time()
        values = self._calc_sine(time)
        return time, values

    def get_derivative(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate time and derivatives based on the tendency. If no time array is
        provided, a linearly spaced time array will be generated from the start to the
        end of the tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = self.generate_time()
        values = self._calc_derivative(time)
        return time, values

    def generate_time(self) -> np.ndarray:
        """Generates time array containing start and end of the tendency."""
        sampling_rate = 100
        num_steps = int(self.duration * sampling_rate) + 1
        return np.linspace(float(self.start), float(self.end), num_steps)

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
