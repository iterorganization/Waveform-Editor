import numpy as np

from waveform_editor.tendencies.base_tendency import BaseTendency


class SineWaveTendency(BaseTendency):
    """ """

    def __init__(self, prev_tendency, base, amplitude, frequency, duration):
        super().__init__(duration, prev_tendency, "sine")
        self.base = base
        self.amplitude = amplitude
        self.frequency = frequency

    def generate(self, sampling_rate):
        num_steps = int(self.duration * sampling_rate)
        time = np.linspace(self.start, self.end, num_steps)
        values = self.base + self.amplitude * np.sin(2 * np.pi * self.frequency * time)
        return time, values
