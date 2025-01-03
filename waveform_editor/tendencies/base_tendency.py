from abc import abstractmethod

import numpy as np
import param


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

    start = param.Number(default=0, bounds=(0, None), doc="Start time of the tendency.")
    duration = param.Number(
        default=1, bounds=(0, None), doc="Duration of the tendency."
    )
    end = param.Number(default=1, bounds=(0, None), doc="End time of the tendency")

    def __init__(self, duration, prev_tendency=None):
        super().__init__()

        self.duration = duration
        self.prev_tendency = prev_tendency
        self._set_previous(prev_tendency)

        self.start = 0 if self.prev_tendency is None else self.prev_tendency.end
        self.end = self.start + self.duration

    def _set_previous(self, prev_tendency):
        """Set the previous tendency and set its next tendency to this instance.

        Args:
            prev_tendency: The tendency that comes before the current tendency. This is
                None if this is the first tendency.
        """
        self.prev_tendency = prev_tendency

        if self.prev_tendency is not None:
            self.prev_tendency.next_tendency = self

    @param.depends("duration", "prev_tendency.end", watch=True)
    def _update_end(self):
        """Automatically update the end when duration or previous tendency changes."""
        self.start = 0 if self.prev_tendency is None else self.prev_tendency.end
        self.end = self.start + self.duration

    @abstractmethod
    def generate(self, time, sampling_rate) -> tuple[np.ndarray, np.ndarray]:
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
        pass
