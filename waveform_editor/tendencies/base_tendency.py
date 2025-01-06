from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np
import param


@dataclass
class TimeInterval:
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

    start = param.Number(default=0, doc="Start time of the tendency.")
    duration = param.Number(
        default=1, bounds=(0, None), doc="Duration of the tendency."
    )
    end = param.Number(default=1, doc="End time of the tendency")

    def __init__(self, prev_tendency, time_interval):
        super().__init__()

        self._set_previous(prev_tendency)
        self._validate_user_input(time_interval)

    def _validate_user_input(self, time_interval):
        """Validates the start, duration, and end values provided by the user, and
        calculates the actual values if not all values are provided.

        Args:
            time_interval: Dataclass containing the start, duration, and end value
            provided by the user.
        """
        user_start = time_interval.start
        user_duration = time_interval.duration
        user_end = time_interval.end

        if (
            user_start is not None
            and user_duration is not None
            and user_end is not None
        ):
            if user_start + user_duration != user_end:
                raise ValueError(
                    "Inputs are inconsistent: start + duration does not equal end."
                )
            self.start = user_start
            self.duration = user_duration
            self.end = user_end
        elif user_start is not None and user_duration is not None:
            self.start = user_start
            self.duration = user_duration
            self.end = user_start + user_duration
        elif user_start is not None and user_end is not None:
            self.start = user_start
            self.end = user_end
            self.duration = user_end - user_start
        elif user_duration is not None and user_end is not None:
            self.duration = user_duration
            self.end = user_end
            self.start = user_end - user_duration
            if self.prev_tendency is not None and not np.isclose(
                self.start, self.prev_tendency.end
            ):
                raise ValueError(
                    "Ambiguous input: no start is provided and the calculated start"
                    "does not equal the end of the previous tendency."
                )
        elif user_duration is not None:
            if self.prev_tendency is None:
                self.start = 0
            else:
                self.start = self.prev_tendency.end
            self.duration = user_duration
            self.end = self.start + self.duration
        elif user_end is not None:
            if self.prev_tendency is None:
                self.start = 0
            else:
                self.start = self.prev_tendency.end
            self.duration = user_end - self.start
            self.end = user_end
        else:
            raise ValueError(
                "Insufficient inputs: Unable to calculate the start, "
                "duration, and end."
            )

    def _set_previous(self, prev_tendency):
        """Set the previous tendency and set its next tendency to this instance.

        Args:
            prev_tendency: The tendency that comes before the current tendency. This is
                None if this is the first tendency.
        """
        self.prev_tendency = prev_tendency

        if self.prev_tendency is not None:
            self.prev_tendency.next_tendency = self

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
    def generate(self, time, sampling_rate) -> tuple[np.ndarray, np.ndarray]:
        """Generate time and values based on the tendency. If no time array is provided,
        a linearly spaced time array will be generated from the start to the end of the
        tendency, with the given sampling rate.

        Args:
            time: The time array on which to generate points.
            sampling_rate: The sampling rate of the generated time array, if no custom
            time array is given.

        Returns:
            Tuple containing the time and its tendency values.
        """
        pass
