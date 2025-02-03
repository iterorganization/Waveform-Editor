import numpy as np

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

        from waveform_editor.waveform import Waveform

        self.waveform = Waveform(waveform_dict)
        super().__init__(**kwargs)
        if self.waveform.tendencies[0].start != 0:
            print(
                "Warning: The starting point of the repeated tendency is not set to 0. "
                "As a result, part of the repeated tendency will be missing "
                "and set to zero."
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

        times = []
        values = []

        if time is None:
            sampling_rate = 100
            num_steps = int(self.duration * sampling_rate) + 1
            times = np.linspace(float(self.start), float(self.end), num_steps)
        else:
            times.extend(time)

        length = self.waveform.calc_length()

        for t in times:
            relative_time = (t - self.start) % length

            _, value = self.waveform.generate(np.array([relative_time]))

            if value.size == 0:
                values.append(0)
            else:
                values.append(value[0])

        times = np.array(times)
        values = np.array(values)
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
