import numpy as np
import param

from waveform_editor.tendencies.base_tendency import BaseTendency


class SineWaveTendency(BaseTendency):
    """A tendency representing a sine wave."""

    base = param.Number(default=0.0, doc="The baseline value of the sine wave.")
    amplitude = param.Number(default=1.0, doc="The amplitude of the sine wave.")
    frequency = param.Number(
        default=1.0, bounds=(0, None), doc="The frequency of the sine wave."
    )

    def __init__(
        self,
        prev_tendency=None,
        base=0.0,
        amplitude=1.0,
        frequency=1.0,
        duration=1.0,
    ):
        super().__init__(duration=duration, prev_tendency=prev_tendency)

        self.base = base
        self.amplitude = amplitude
        self.frequency = frequency

    def generate(self, time=None, sampling_rate=100):
        """Generate time and values based on the tendency. If no time array is provided,
        A linearly spaced time array will be generate from the start to the end of
        tendency, with the given sampling rate.

        Args:
            time: The time array on which to generate points.
            sampling_rate: The sampling rate of the generate time array, if no custom
            time array is given.

        Returns:
            Tuple containing the time and and its the tendency values.
        """
        if time is None:
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(float(self.start), float(self.end), num_steps)
        values = self.base + self.amplitude * np.sin(2 * np.pi * self.frequency * time)
        return time, values
