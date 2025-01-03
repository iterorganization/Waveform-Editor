from abc import abstractmethod

import numpy as np
import param


class BaseTendency(param.Parameterized):
    """
    Base class for different types of tendencies.
    """

    prev_tendency = param.ClassSelector(
        class_=param.Parameterized, default=None, instantiate=False
    )
    next_tendency = param.ClassSelector(
        class_=param.Parameterized, default=None, instantiate=False
    )
    start = param.Number(default=0, bounds=(0, None))
    duration = param.Number(default=1, bounds=(0, None))
    end = param.Number(default=1, bounds=(0, None))

    def __init__(self, duration, prev_tendency=None, **params):
        super().__init__(**params)

        # Initialize parameters
        self.duration = duration
        self.prev_tendency = prev_tendency
        self._set_previous(prev_tendency)

        # Update start and end based on previous tendency
        self.start = 0 if self.prev_tendency is None else self.prev_tendency.end
        self.end = self.start + self.duration

    def _set_previous(self, prev_tendency):
        """Set the previous tendency and link it to this instance."""
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
        """Generate time and values based on the tendency."""
        pass
