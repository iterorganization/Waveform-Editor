import numpy as np
from scipy.interpolate import CubicSpline

from waveform_editor.tendencies.base_tendency import BaseTendency


class SmoothTendency(BaseTendency):
    """ """

    def __init__(self, prev_tendency, from_value=None, to_value=None, duration=None):
        super().__init__(duration, prev_tendency)

        self.from_value = from_value
        self.to_value = to_value

    def generate(self, time=None, sampling_rate=100):
        if time is None:
            num_steps = int(self.duration * sampling_rate) + 1
            time = np.linspace(float(self.start), float(self.end), num_steps)

        spline = CubicSpline(
            [self.start, self.end],
            [self.from_value, self.to_value],
            bc_type=((1, 0), (1, 0)),
        )
        values = spline(time)
        return time, values
