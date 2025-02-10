from typing import Optional

import numpy as np

from waveform_editor.annotations import Annotations
from waveform_editor.tendencies.base import BaseTendency


class RepeatTendency(BaseTendency):
    """
    Tendency class for a repeated signal.
    """

    def __init__(self, **kwargs):
        waveform_dict = []
        if "user_waveform" in kwargs:
            waveform_dict = kwargs.pop("user_waveform")
        super().__init__(**kwargs)

        for item in waveform_dict:
            if item.get("type") == "piecewise":
                self.value_error = ValueError(
                    "Piecewise tendencies are currently not supported inside of a "
                    "repeated tendency."
                )

        from waveform_editor.waveform import Waveform

        self.waveform = Waveform(waveform_dict)
        if not self.waveform.tendencies:
            return

        if self.waveform.tendencies[0].start != 0:
            self.value_error = ValueError(
                "The starting point of the first repeated tendency is not set to 0."
            )

        # Link the last tendency to the first tendency in the repeated waveform
        # We must lock the start to 0, otherwise it will take the start value of the
        # previous tendency.
        self.waveform.tendencies[0].user_start = 0
        self.waveform.tendencies[0].set_previous_tendency(self.waveform.tendencies[-1])
        self.waveform.tendencies[-1].set_next_tendency(self.waveform.tendencies[0])

        self.annotations.add_annotations(self.waveform.annotations)

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If no time array is
        provided, the individual tendencies are responsible for creating a time array,
        and these are appended.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if not self.waveform.tendencies:
            return np.array([]), np.array([])
        length = self.waveform.calc_length()
        if time is None:
            time, values = self.waveform.get_value()
            repeat = int(np.ceil(self.duration / length))
            repetition_array = np.arange(repeat) * length
            time = (time + repetition_array[:, np.newaxis]).flatten() + self.start
            values = np.tile(values, repeat)

            # cut off everything after self.end
            assert time[-1] >= self.end
            cut_index = np.argmax(time >= self.end)
            time = time[: cut_index + 1]

            values = values[: cut_index + 1]
            if time[-1] != self.end:
                time[-1] = self.end
                _, end_array = self.waveform.get_value(
                    np.array([(self.end - self.start) % length])
                )
                values[-1] = end_array[0]
        else:
            relative_times = (time - self.start) % length
            _, values = self.waveform.get_value(relative_times)
        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        length = self.waveform.calc_length()
        relative_times = (time - self.start) % length
        derivatives = self.waveform.get_derivative(relative_times)
        return derivatives
