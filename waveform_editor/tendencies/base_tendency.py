from abc import ABC, abstractmethod

import numpy as np


class BaseTendency(ABC):
    """
    Base class for different types of tendencies.
    """

    def __init__(self, duration, prev_tendency, tendency_type):
        self.prev_tendency = None
        self.next_tendency = None
        self._set_previous(prev_tendency)

        start = 0 if self.prev_tendency is None else prev_tendency.end

        self.start = start
        self.duration = duration
        self.end = start + duration
        self.tendency_type = tendency_type

        self._validate()

    def _set_previous(self, prev_tendency):
        self.prev_tendency = prev_tendency

        if self.prev_tendency is not None:
            self.prev_tendency.next_tendency = self

    def _validate(self):
        assert self.start is not None, "Start value could not be determined."
        assert self.duration is not None, "duration could not be determined."
        assert self.end is not None, "End value could not be determined."
        assert self.start <= self.end, "The end value should be later than the start"

    @abstractmethod
    def generate(self, sampling_rate) -> tuple[np.ndarray, np.ndarray]:
        pass
