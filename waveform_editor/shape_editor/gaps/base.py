"""What all machines' gaps have in common."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MeasuredGap:
    """A gap as measured on a plasma boundary."""

    key: str  # The name of the gap, in the GAP_METADATA of its machine
    orig: tuple  # The (r, z) it is measured from
    target: tuple  # The (r, z) it is measured to
    distance: float | None  # In metres, None if it could not be measured


class MachineGaps(ABC):
    """The gaps between a plasma and the machine around it, as one machine defines
    them."""

    # (symbol, unit, full name) of each gap, by name
    GAP_METADATA = {}

    @abstractmethod
    def gap_inputs(self, time_slice):
        """The arguments of measure for a solved equilibrium.

        Args:
            time_slice: The equilibrium time slice.
        """

    @abstractmethod
    def measure(self, outline_r, outline_z, *args, **kwargs):
        """The MeasuredGap of each gap of a plasma boundary."""

    def compute_gaps(self, *args, **kwargs):
        """The gaps in metres by name, None for those that could not be measured.
        Takes the arguments of measure."""
        return {gap.key: gap.distance for gap in self.measure(*args, **kwargs)}
