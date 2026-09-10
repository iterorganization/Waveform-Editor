import logging

import numpy as np

from waveform_editor.base_waveform import BaseWaveform
from waveform_editor.imports import INTERP_MODES

logger = logging.getLogger(__name__)


class CopyWaveform(BaseWaveform):
    """A waveform whose value is taken from one of the configuration's imports.

    ``{copy: scenario}`` reads this waveform's own DD path from the ``scenario`` import;
    ``path:`` reads a different one, which is what a waveform whose name is not a DD
    path needs. ``interp:`` (``closest`` by default) says how the source is resampled
    onto the export time base when the two differ.

    A 0D copy behaves like any other waveform -- :meth:`get_value` returns one value per
    time -- so it can be plotted and used in expressions. Anything larger (a profile, a
    per-slice array, time-independent structure) has no such curve; the exporter copies
    it straight into the target IDS instead, and :attr:`is_structural` says so.
    """

    def __init__(self, entry, *, yaml_str="", name="waveform", dd_version=None):
        super().__init__(yaml_str, name, dd_version)
        self.yaml_str = yaml_str
        self.line_number = entry.get("line_number", 0)
        self.ref = entry.get("user_copy", "")
        self.path = entry.get("user_path") or None
        interp = entry.get("user_interp", "closest")
        if interp not in INTERP_MODES:
            self.annotations.add(
                self.line_number,
                f"Unknown interp '{interp}', expected one of "
                f"{', '.join(INTERP_MODES)}.",
            )
            interp = "closest"
        self.interp = interp
        if not self.ref:
            self.annotations.add(self.line_number, "copy: must name an import.")

    @property
    def source_path(self):
        """The DD path read from the source: ``path:`` if given, else our own name."""
        return self.path or self.name

    @property
    def is_structural(self):
        """Whether this copy must be written into the IDS wholesale, rather than as one
        value per time step. True for anything that is not a 0D dynamic node -- and for
        a waveform whose name is not a DD path at all, provided ``path:`` says what to
        read.

        A 0D dynamic node is one value per time only when nothing else along the path
        multiplies it. An explicit index or slice does: ``equilibrium/time_slice/
        global_quantities/ip`` is a single curve, but ``core_sources/source(:)/
        profiles_1d/time`` is one per source -- and those need not even be the same
        length, since a source with no profiles_1d has none of them.
        """
        if self.metadata is None:
            return self.path is None
        if not (self.metadata.ndim == 0 and self.metadata.type.is_dynamic):
            return True
        return "(" in self.name or "(" in self.source_path

    def get_value(self, time: np.ndarray | None = None):
        """One value per time for a 0D copy; an empty curve for anything else.

        Reading needs the configuration's
        :class:`~waveform_editor.imports.ImportReader`, which is attached by the
        configuration as ``self.reader``.
        """
        if time is None:
            time = np.array([])
        reader = getattr(self, "reader", None)
        if reader is None or self.is_structural or time.size == 0:
            return time, np.zeros_like(time, dtype=float)
        return time, reader.sample(self.ref, self.source_path, time, self.interp)

    def fill_into(self, ids, time, reader):
        """Copy this waveform's source node into ``ids``."""
        reader.copy_into(ids, self.ref, self.source_path, self.name, time, self.interp)

    def get_yaml_string(self) -> str:
        return self.yaml_str
