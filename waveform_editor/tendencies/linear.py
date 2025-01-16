import numpy as np
import param
from param import depends

from waveform_editor.tendencies.base import BaseTendency


class LinearTendency(BaseTendency):
    """
    Linear tendency class for a signal with a linear increase or decrease.
    """

    from_ = param.Number(
        default=0.0,
        doc="The calculated value at the start of the linear tendency.",
    )
    user_from = param.Number(
        default=0.0,
        doc="The value at the start of the linear tendency, as provided by the user.",
        allow_None=True,
    )

    to = param.Number(
        default=1.0,
        doc="The calculated value at the end of the linear tendency.",
    )
    user_to = param.Number(
        default=1.0,
        doc="The value at the end of the linear tendency, as provided by the user.",
        allow_None=True,
    )

    rate = param.Number(
        default=1.0,
        doc="The calculated rate of change of the linear tendency.",
    )
    user_rate = param.Number(
        default=1.0,
        doc="The  rate of change of the linear tendency, as provided by the user.",
        allow_None=True,
    )

    def __init__(
        self,
        *,
        start=None,
        duration=None,
        end=None,
        from_=None,
        to=None,
        rate=None,
    ):
        super().__init__(start, duration, end)
        self.user_from = from_
        self.user_to = to
        self.user_rate = rate

        self._validate_linear_input()

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a line containing the start and end points will be generated.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time = np.array([self.start, self.end])
        values = np.linspace(self.from_, self.to, len(time))
        return time, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.from_

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.to

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        return self.rate

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        return self.rate

    @depends("prev_tendency", "next_tendency", watch=True)
    def _validate_linear_input(self):
        """Determines the from, to and rate values based on the provided user input.
        If values are missing, it will infer the values based on previous or next
        tendencies. If there are none, it will use the default values for that
        param."""
        if (
            self.user_from is not None
            and self.user_to is not None
            and self.user_rate is not None
        ):
            calculated_rate = (self.user_to - self.user_from) / self.duration
            if not np.isclose(self.user_rate, calculated_rate):
                raise ValueError(
                    "The rate of change does not match to and from values."
                )
            self.from_ = self.user_from
            self.to = self.user_to
            self.rate = self.user_rate
        elif self.user_from is not None and self.user_to is not None:
            self.from_ = self.user_from
            self.to = self.user_to
            self.rate = (self.to - self.from_) / self.duration
        elif self.user_from is not None and self.user_rate is not None:
            self.from_ = self.user_from
            self.rate = self.user_rate
            self.to = self.rate * self.duration + self.from_
        elif self.user_rate is not None and self.user_to is not None:
            self.to = self.user_to
            self.rate = self.user_rate
            self.from_ = self.to - self.rate * self.duration
        elif self.user_from is not None:
            self.from_ = self.user_from
            if self.next_tendency is not None:
                self.to = self.next_tendency.get_start_value()
            self.rate = (self.to - self.from_) / self.duration
        elif self.user_rate is not None:
            self.rate = self.user_rate
            if self.prev_tendency is not None:
                self.from_ = self.prev_tendency.get_end_value()
                self.to = self.rate * self.duration + self.from_
            elif self.next_tendency is not None:
                self.to = self.next_tendency.get_start_value()
                self.from_ = self.to - self.rate * self.duration
            else:
                self.to = self.rate * self.duration + self.from_
                self.from_ = self.to - self.rate * self.duration
        elif self.user_to is not None:
            self.to = self.user_to
            if self.prev_tendency is not None:
                self.from_ = self.prev_tendency.get_end_value()
            self.rate = (self.to - self.from_) / self.duration
        else:
            if self.next_tendency is not None:
                self.to = self.next_tendency.get_start_value()
            if self.prev_tendency is not None:
                self.from_ = self.prev_tendency.get_end_value()
            self.rate = (self.to - self.from_) / self.duration

        calculated_rate = (self.to - self.from_) / self.duration
        if not np.isclose(self.rate, calculated_rate):
            raise ValueError("Rate does not match the provided to and from values.")
