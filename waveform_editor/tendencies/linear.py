import numpy as np

from waveform_editor.tendencies.base_tendency import BaseTendency


class LinearTendency(BaseTendency):
    """
    Linear tendency class for a signal with a linear increase or decrease.
    """

    def __init__(self, prev_tendency, from_value=None, to_value=None, duration=None):
        super().__init__(duration, prev_tendency)
        self.from_value = from_value
        self.to_value = to_value

    def generate(self, time=None, sampling_rate=100):
        if time is None:
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(self.start, self.end, num_steps)
        values = np.linspace(self.from_value, self.to_value, len(time))
        return time, values
