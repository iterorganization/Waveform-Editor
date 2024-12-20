import numpy as np

from waveform_editor.tendencies.base_tendency import BaseTendency


class LinearTendency(BaseTendency):
    """
    Linear tendency class for a signal with a linear increase or decrease.
    """

    def __init__(self, from_value, to_value, duration, prev_end):
        super().__init__(prev_end, duration, prev_end, "linear")
        self.from_value = from_value
        self.to_value = to_value

    def generate(self, sampling_rate):
        num_steps = int(self.duration * sampling_rate)
        time = np.linspace(self.start, self.end, num_steps)
        values = np.linspace(self.from_value, self.to_value, num_steps)
        return time, values
