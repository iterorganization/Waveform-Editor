from abc import ABC, abstractmethod

import numpy as np


class BaseTendency(ABC):
    """
    Base class for different types of tendencies.
    """

    def __init__(self, duration, prev_tendency, tendency_type):
        start = 0 if prev_tendency is None else prev_tendency.end

        self.start = start
        self.duration = duration
        self.end = start + duration
        self.prev_tendency = prev_tendency
        self.tendency_type = tendency_type

        self._validate()

    def _validate(self):
        assert self.start is not None
        assert self.duration is not None
        assert self.end is not None
        assert self.start <= self.end

    @abstractmethod
    def generate(self, sampling_rate) -> tuple[np.ndarray, np.ndarray]:
        pass
