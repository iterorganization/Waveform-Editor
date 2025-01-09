from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np
import param
from param import depends


@dataclass
class TimeInterval:
    """
    Dataclass which stores the time interval (start, duration, and end) of a tendency.
    """

    start: Optional[float] = None
    duration: Optional[float] = None
    end: Optional[float] = None


class BaseTendency(param.Parameterized):
    """
    Base class for different types of tendencies.
    """

    prev_tendency = param.ClassSelector(
        class_=param.Parameterized,
        default=None,
        instantiate=False,
        doc="The tendency that precedes the current tendency.",
    )
    next_tendency = param.ClassSelector(
        class_=param.Parameterized,
        default=None,
        instantiate=False,
        doc="The tendency that follows the current tendency.",
    )

    start = param.Number(default=0.0, doc="The calculated start time of the tendency.")
    user_start = param.Number(
        default=0.0,
        doc="The start time of the tendency, as provided by the user.",
        allow_None=True,
    )

    duration = param.Number(
        default=1.0, bounds=(0.0, None), doc="The calculated duration of the tendency."
    )
    user_duration = param.Number(
        default=1.0,
        bounds=(0.0, None),
        doc="The duration of the tendency, as provided by the user.",
        allow_None=True,
    )

    end = param.Number(default=1.0, doc="The calculated end time of the tendency.")
    user_end = param.Number(
        default=1.0,
        doc="The end time of the tendency, as provided by the user.",
        allow_None=True,
    )

    def __init__(self, time_interval):
        super().__init__()

        self.user_start = time_interval.start
        self.user_duration = time_interval.duration
        self.user_end = time_interval.end
        self._validate_user_input()

    def set_previous_tendency(self, prev_tendency):
        """Sets the previous tendency as a param.

        Args:
            prev_tendency: The tendency precedes the current tendency.
        """
        self.prev_tendency = prev_tendency

    def set_next_tendency(self, next_tendency):
        """Sets the next tendency as a param.

        Args:
            next_tendency: The tendency follows the current tendency.
        """
        self.next_tendency = next_tendency

    @abstractmethod
    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        pass

    @abstractmethod
    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        pass

    @abstractmethod
    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        pass

    @abstractmethod
    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        pass

    @abstractmethod
    def generate(self, time) -> tuple[np.ndarray, np.ndarray]:
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        pass

    @depends("prev_tendency", "next_tendency", watch=True)
    def _validate_user_input(self):
        """Validates the user-defined start, duration, and end values. If one or more
        are missing, they are calculated based on the given values, or by neighbouring
        tendencies. The calculated start, duration, and end values are stored in their
        respective params.
        """

        if (
            self.user_start is not None
            and self.user_duration is not None
            and self.user_end is not None
        ):
            if self.user_start + self.user_duration != self.user_end:
                raise ValueError(
                    "Inputs are inconsistent: start + duration does not equal end."
                )
            self.start = self.user_start
            self.duration = self.user_duration
            self.end = self.user_end
        elif self.user_start is not None and self.user_duration is not None:
            self.start = self.user_start
            self.duration = self.user_duration
            self.end = self.user_start + self.user_duration
        elif self.user_start is not None and self.user_end is not None:
            self.start = self.user_start
            self.end = self.user_end
            self.duration = self.user_end - self.user_start
        elif self.user_duration is not None and self.user_end is not None:
            self.duration = self.user_duration
            self.end = self.user_end
            self.start = self.user_end - self.user_duration
            if self.prev_tendency is not None and not np.isclose(
                self.start, self.prev_tendency.end
            ):
                raise ValueError(
                    "Ambiguous input: no start is provided and the calculated start"
                    "does not equal the end of the previous tendency."
                )
        elif self.user_duration is not None:
            if self.prev_tendency is None:
                self.start = 0
            else:
                self.start = self.prev_tendency.end
            self.duration = self.user_duration
            self.end = self.start + self.duration
        elif self.user_end is not None:
            if self.prev_tendency is None:
                self.start = 0
            else:
                self.start = self.prev_tendency.end
            self.duration = self.user_end - self.start
            self.end = self.user_end
        else:
            raise ValueError(
                "Insufficient inputs: Unable to calculate the start, duration, and end."
            )
