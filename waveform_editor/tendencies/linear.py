import numpy as np

from waveform_editor.tendencies.base_tendency import BaseTendency


class LinearTendency(BaseTendency):
    """
    Linear tendency class for a signal with a linear increase or decrease.
    """

    def __init__(self, prev_tendency, from_value, to_value, duration):
        super().__init__(duration, prev_tendency, "linear")
        self.from_value = from_value
        self.to_value = to_value

    def generate(self, sampling_rate):
        num_steps = int(self.duration * sampling_rate)
        time = np.linspace(self.start, self.end, num_steps)
        values = np.linspace(self.from_value, self.to_value, num_steps)
        return time, values
