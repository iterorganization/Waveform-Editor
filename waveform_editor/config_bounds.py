import logging

from waveform_editor.derived_waveform import DerivedWaveform

logger = logging.getLogger(__name__)


class ConfigurationBounds:
    """
    Manages the first and last waveforms in a collection.
    """

    def __init__(self, config):
        """
        Initializes the WaveformBounds manager.
        """
        self.config = config
        self.first_waveform = None
        self.last_waveform = None

    def update_for_add(self, waveform):
        """
        Updates the bounds when a new waveform is added.

        Args:
            waveform: The waveform being added.
        """
        if not waveform.tendencies:
            return

        if self.first_waveform is None:
            self.first_waveform = waveform
            self.last_waveform = waveform
            return

        if waveform.tendencies[0].start < self.first_waveform.tendencies[0].start:
            self.first_waveform = waveform

        if waveform.tendencies[-1].end > self.last_waveform.tendencies[-1].end:
            self.last_waveform = waveform

    def needs_recalc(self, waveform):
        """
        Checks if the bounds need to be recalculated after a change to the given waveform.

        Args:
            waveform: The waveform that has changed.

        Returns:
            True if a recalculation is needed, False otherwise.
        """
        if self.first_waveform is None:
            return False

        is_first = self.first_waveform.name == waveform.name
        is_last = self.last_waveform.name == waveform.name
        return is_first or is_last

    def recalculate(self):
        """
        Recalculates the first and last waveforms from the entire collection.

        Args:
            waveform_map: A dictionary mapping waveform names to their groups.
            get_waveform: A function to retrieve a waveform object by its name.
        """
        min_start = float("inf")
        max_end = float("-inf")
        self.first_waveform = None
        self.last_waveform = None

        for name in self.config.waveform_map:
            waveform = self.config[name]
            if not isinstance(waveform, DerivedWaveform) and waveform.tendencies:
                if waveform.tendencies[0].start < min_start:
                    min_start = waveform.tendencies[0].start
                    self.first_waveform = waveform
                if waveform.tendencies[-1].end > max_end:
                    max_end = waveform.tendencies[-1].end
                    self.last_waveform = waveform

    def clear(self):
        """
        Resets the first and last waveforms.
        """
        self.first_waveform = None
        self.last_waveform = None
