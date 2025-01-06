import numpy as np
import param
from scipy.interpolate import CubicSpline

from waveform_editor.tendencies.base_tendency import BaseTendency


class SmoothTendency(BaseTendency):
    """
    Smooth tendency class for a signal with a cubic spline interpolation.
    """

    from_value = param.Number(
        default=0.0,
        doc="The starting value of the smooth tendency.",
    )
    to_value = param.Number(
        default=1.0, bounds=(None, None), doc="The ending value of the smooth tendency."
    )

    def __init__(self, prev_tendency, time_interval, from_value=0.0, to_value=1.0):
        super().__init__(prev_tendency, time_interval)

        self.from_value = from_value
        self.to_value = to_value

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

        spline = CubicSpline(
            [self.start, self.end],
            [self.from_value, self.to_value],
            bc_type=((1, 0), (1, 0)),
        )
        values = spline(time)
        return time, values
