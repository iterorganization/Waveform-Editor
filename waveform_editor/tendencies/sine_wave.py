import numpy as np
import param
from param import depends

from waveform_editor.tendencies.base_tendency import BaseTendency


class SineWaveTendency(BaseTendency):
    """A tendency representing a sine wave."""

    base = param.Number(default=0.0, doc="The baseline value of the sine wave.")
    user_base = param.Number(
        default=0.0,
        doc="The baseline value of the sine wave provided by the user.",
        allow_None=True,
    )

    amplitude = param.Number(default=1.0, doc="The amplitude of the sine wave.")
    frequency = param.Number(
        default=1.0, bounds=(0, None), doc="The frequency of the sine wave."
    )

    def __init__(self, time_interval, base=None, amplitude=1.0, frequency=1.0):
        super().__init__(time_interval)
        self.user_base = base

        self.amplitude = amplitude
        self.frequency = frequency
        self._update_base()

    def generate(self, time=None, sampling_rate=100):
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency, with the given sampling rate.

        Args:
            time: The time array on which to generate points.
            sampling_rate: The sampling rate of the generated time array, if no custom
            time array is given.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
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

    @depends("next_tendency", "prev_tendency", watch=True)
    def _update_base(self):
        """Update the base of the sine wave. If the `base` keyword is given explicitly
        by the user, this value is used. Otherwise, if there exists a previous or next
        tendency, its last value will be chosen. If neither exist, it is set to the
        default value."""
        if self.user_base is None:
            if self.prev_tendency is not None:
                self.base = self.prev_tendency.get_end_value()
            elif self.next_tendency is not None:
                self.base = self.next_tendency.get_start_value()
        else:
            self.base = self.user_base
