from typing import Optional

import numpy as np
import param

from waveform_editor.tendencies.base import BaseTendency


class RepeatTendency(BaseTendency):
    """
    Tendency class for a repeated signal.
    """

    user_frequency = param.Number(
        default=None,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        doc="The frequency of the repeated waveform, as provided by the user.",
    )
    user_period = param.Number(
        default=None,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        doc="The period of the repeated waveform, as provided by the user.",
    )

    def __init__(self, **kwargs):
        waveform = kwargs.pop("user_waveform", []) or []
        from waveform_editor.waveform import Waveform

        self.waveform = Waveform(waveform=waveform, is_repeated=True)
        self.period = 1
        super().__init__(**kwargs)
        if not self.waveform.tendencies:
            error_msg = "There are no tendencies in the repeated waveform.\n"
            self.annotations.add(self.line_number, error_msg)
            return

        if self.waveform.tendencies[0].start != 0:
            error_msg = (
                "The starting point of the first repeated tendency must be set to 0.\n"
            )
            self.annotations.add(self.line_number, error_msg)

        # Link the last tendency to the first tendency in the repeated waveform
        # We must lock the start to 0, otherwise it will take the start value of the
        # previous tendency.
        self.waveform.tendencies[0].user_start = 0
        self.waveform.tendencies[0].set_previous_tendency(self.waveform.tendencies[-1])
        self.waveform.tendencies[-1].set_next_tendency(self.waveform.tendencies[0])

        self._set_period()
        self.values_changed = True
        self.annotations.add_annotations(self.waveform.annotations)

    def _set_period(self):
        """Sets the period of the repeated waveform. If no period or frequency are
        provided by the user, the period is set to the combined length of the
        tendencies.
        """

        if self.user_frequency is not None:
            if self.user_period is not None and not np.isclose(
                self.user_frequency, 1 / self.user_period
            ):
                error_msg = (
                    "The frequency and period do not match! (freq != 1 / period).\n"
                    "The period will be ignored and only the frequency is used.\n"
                )
                self.annotations.add(self.line_number, error_msg, is_warning=True)
            self.period = 1 / self.user_frequency
        elif self.user_period is not None:
            self.period = self.user_period
        else:
            self.period = self.waveform.tendencies[-1].end

        length = self.waveform.calc_length()
        scaling_factor = self.period / length
        if self.duration < length * scaling_factor:
            error_msg = (
                "The repeated tendency has not completed a single repetition.\n"
                "Perhaps increase the duration of the repeated tendency?\n"
            )
            self.annotations.add(self.line_number, error_msg, is_warning=True)

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
            return np.array([0]), np.array([0])
        length = self.waveform.calc_length()
        scaling_factor = self.period / length

        if time is None:
            time, values = self.waveform.get_value()

            # Compute how many full cycles fit in duration
            repeat = int(np.ceil(self.duration / self.period))
            repetition_array = np.arange(repeat) * self.period

            time = (
                (time * scaling_factor) + repetition_array[:, np.newaxis]
            ).flatten() + self.start
            values = np.tile(values, repeat)

            # cut off everything after self.end
            if not np.isclose(time[-1], self.end):
                assert time[-1] >= self.end
                cut_index = np.argmax(time >= self.end)
                time = time[: cut_index + 1]
                values = values[: cut_index + 1]

            if time[-1] != self.end:
                time[-1] = self.end
                _, end_array = self.waveform.get_value(
                    np.array([((self.end - self.start) % self.period) / scaling_factor])
                )
                values[-1] = end_array[0]
        else:
            relative_times = ((time - self.start) % self.period) / scaling_factor
            _, values = self.waveform.get_value(relative_times)
        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        if not self.waveform.tendencies:
            return np.array([0])

        length = self.waveform.calc_length()
        repeat_factor = self.period / length

        relative_times = ((time - self.start) % self.period) / repeat_factor
        derivatives = self.waveform.get_derivative(relative_times) / repeat_factor

        return derivatives
