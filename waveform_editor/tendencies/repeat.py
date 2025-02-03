import numpy as np

from waveform_editor import waveform
from waveform_editor.tendencies.base import BaseTendency


class RepeatTendency(BaseTendency):
    """
    Tendency class for a repeated signal.
    """

    def __init__(self, **kwargs):
        waveform_dict = kwargs.pop("user_waveform")

        for item in waveform_dict:
            if item.get("type") == "piecewise":
                self.value_error = ValueError(
                    "Piecewise tendencies are currently not supported inside of a "
                    "repeated tendency."
                )

        self.waveform = waveform.Waveform(waveform_dict)
        super().__init__(**kwargs)
        if self.waveform.tendencies[0].start != 0:
            self.value_error = ValueError(
                "The starting point of the first repeated tendency is not set to 0."
            )

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """

        length = self.waveform.calc_length()
        if time is None:
            times, values = self.waveform.generate()
            repeat = int(np.ceil(self.duration / length))
            repetition_array = np.arange(repeat) * length
            times = (times + repetition_array[:, np.newaxis]).flatten() + self.start
            values = np.tile(values, repeat)

            # cut off everything after self.end
            assert times[-1] >= self.end
            cut_index = np.argmax(times >= self.end)
            times = times[: cut_index + 1]

            values = values[: cut_index + 1]
            if times[-1] != self.end:
                times[-1] = self.end
                _, end_value = self.waveform.generate((self.end - self.start) % length)

                # If there are gaps in the repeated waveform, it might try to generate
                # a value at a time where there is no tendency. In this case, the value
                # is set to 0.
                if end_value.size == 0:
                    values[-1] = 0
                else:
                    values[-1] = end_value
        else:
            times = np.atleast_1d(time)
            relative_times = (times - self.start) % length
            _, values = self.waveform.generate(relative_times)

        return times, values

    # FIXME: Implicitly linking start and end values does not work yet. For example:
    # waveform:
    # - {type: linear, from: 2, duration: 2}
    # - type: repeat
    #   duration: 8
    #   waveform:
    #   - {type: linear, from: 1, to: 2, duration: 1}
    #   - {type: constant, value: 1, duration: 0.5}
    #   - {type: sine-wave, base: 1, amplitude: -1, frequency: 0.25, duration: 1}
    # - {type: linear, to: 2, duration: 2}

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.generate(self.start)

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.generate(self.end)

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        # TODO:
        return 0

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        # TODO:
        return 0
