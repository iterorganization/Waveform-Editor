from typing import Optional

import numpy as np

from waveform_editor.tendencies.periodic.periodic_base import PeriodicBaseTendency


class SineWaveTendency(PeriodicBaseTendency):
    """A tendency representing a sine wave."""

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If no time array is
        provided, a linearly spaced time array will be generated from the start to the
        end of the tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            sampling_rate = 32 * self.frequency
            num_steps = int(self.duration * sampling_rate) + 1
            # Choosing prime number instead of 100k to reduce aliasing artifacts
            num_steps = min(num_steps, 100003)
            time = np.linspace(float(self.start), float(self.end), num_steps)
        values = self._calc_sine(time)
        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        return (
            self.amplitude
            * 2
            * np.pi
            * self.frequency
            * np.cos(2 * np.pi * self.frequency * (time - self.start) + self.phase)
        )

    def _calc_sine(self, time):
        """Returns the value of the sine wave."""
        return self.base + self.amplitude * np.sin(
            2 * np.pi * self.frequency * (time - self.start) + self.phase
        )
