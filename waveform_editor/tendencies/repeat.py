import numpy as np

from waveform_editor.tendencies.base import BaseTendency


class RepeatTendency(BaseTendency):
    """
    Tendency class for a repeated signal.
    """

    def __init__(self, **kwargs):
        waveform_dict = kwargs.pop("user_waveform")

        from waveform_editor.waveform import Waveform

        self.waveform = Waveform(waveform_dict)
        super().__init__(**kwargs)

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a constant line containing the start and end points will be generated.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """

        times = []
        values = []

        if time is None:
            sampling_rate = 100
            num_steps = int(self.duration * sampling_rate) + 1
            times = np.linspace(float(self.start), float(self.end), num_steps)

        length = self.waveform.calc_length()

        for t in times:
            relative_time = (t - self.start) % length

            _, value = self.waveform.generate([relative_time])

            values.append(value[0])

        times = np.array(times)
        values = np.array(values)
        return times, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.waveform.get_start_value()

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.waveform.get_end_value()

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.waveform.get_derivative_start()

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self.waveform.get_derivative_end()
