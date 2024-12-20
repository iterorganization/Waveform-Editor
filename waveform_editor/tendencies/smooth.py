import numpy as np

from waveform_editor.tendencies.base_tendency import BaseTendency


class SmoothTendency(BaseTendency):
    """ """

    def __init__(self, prev_tendency, from_value=None, to_value=None, duration=None):
        super().__init__(duration, prev_tendency, "smooth")

        self.from_value = from_value
        self.to_value = to_value

    def generate(self, sampling_rate):
        num_steps = int(self.duration * sampling_rate)
        time = np.linspace(self.start, self.end, num_steps)

        # Sigmoid function
        center = (self.start + self.end) / 2
        alpha = 3.0
        values = self.from_value + (self.to_value - self.from_value) / 2 * (
            1 + np.tanh(alpha * (time - center))
        )
        return time, values
