from typing import Optional

import numpy as np

from waveform_editor.tendencies.base import BaseTendency


class RepeatTendency(BaseTendency):
    """
    Tendency class for a repeated signal.
    """

    def __init__(self, **kwargs):
        if "user_waveform" not in kwargs:
            self.value_error = ValueError("A repeated tendency must contain a waveform")
            return
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
            self.value_error = ValueError(
                "The starting point of the first repeated tendency is not set to 0."
            )

        # TODO: The start of the first tendency does not link to the end of the last
        # tendency. This might be nice to implement so you could do for example:
        # waveform:
        # - type: repeat
        #   duration: 10
        #   waveform:
        #   - {type: linear, from: 1, to: 2, duration: 1}
        #   - {type: linear, from: 2, to: 0, duration: 1}
        #   - {type: smooth, duration: 3}
        #
        # Here, the smooth tendency would smoothly interpolate from 0 to 2

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate time and values based on the tendency. If no time array is provided,
        the individual tendencies are responsible for creating a time array, and these
        are appended.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        length = self.waveform.calc_length()
        if time is None:
            times, values = self.waveform.get_value()
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
                _, values[-1] = self.waveform.get_value(
                    np.array([(self.end - self.start) % length])
                )
        else:
            times = np.atleast_1d(time)
            relative_times = (times - self.start) % length
            _, values = self.waveform.get_value(relative_times)
        return times, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the derivative values on the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        length = self.waveform.calc_length()
        times = np.atleast_1d(time)
        relative_times = (times - self.start) % length
        derivatives = self.waveform.get_derivative(relative_times)
        return derivatives
