from abc import ABC, abstractmethod

import numpy as np


class BaseTendency(ABC):
    """
    Base class for different types of tendencies.
    """

    def __init__(self, start, duration, prev_end, tendency_type):
        self.start = start
        self.duration = duration
        self.end = start + duration
        self.prev_end = prev_end
        self.tendency_type = tendency_type

        self._validate()

    def _validate(self):
        assert self.start is not None
        assert self.duration is not None
        assert self.end is not None
        assert self.prev_end is not None
        assert self.start >= self.prev_end

    @abstractmethod
    def generate(self, sampling_rate) -> tuple[np.ndarray, np.ndarray]:
        pass
