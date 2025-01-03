import numpy as np
import param

from waveform_editor.tendencies.base_tendency import BaseTendency


class ConstantTendency(BaseTendency):
    """
    Constant tendency class for a constant signal.
    """

    value = param.Number(
        default=0.0, bounds=(None, None), doc="The constant value of the signal."
    )

    def __init__(self, prev_tendency=None, value=0.0, duration=1.0):
        self.value = value
        super().__init__(duration=duration, prev_tendency=prev_tendency)

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
            time = np.linspace(self.start, self.end, num_steps)
        values = np.linspace(self.value, self.value, len(time))
        return time, values
