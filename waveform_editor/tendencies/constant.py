import numpy as np

from waveform_editor.tendencies.base_tendency import BaseTendency


class ConstantTendency(BaseTendency):
    """
    Constant tendency class for a constant signal.
    """

    def __init__(self, prev_tendency, value=None, duration=None):
        self.value = value
        super().__init__(duration, prev_tendency, "constant")

    def generate(self, time=None, sampling_rate=100):
        if time is None:
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(self.start, self.end, num_steps)
        values = np.linspace(self.value, self.value, len(time))
        return time, values
