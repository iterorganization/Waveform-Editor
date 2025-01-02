import numpy as np

from waveform_editor.tendencies.base_tendency import BaseTendency


class SineWaveTendency(BaseTendency):
    """ """

    def __init__(
        self, prev_tendency, base=None, amplitude=None, frequency=None, duration=None
    ):
        super().__init__(duration, prev_tendency, "sine")
        self.base = base
        self.amplitude = amplitude
        self.frequency = frequency

    def generate(self, time=None, sampling_rate=100):
        if time is None:
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(float(self.start), float(self.end), num_steps)
        values = self.base + self.amplitude * np.sin(2 * np.pi * self.frequency * time)
        return time, values
