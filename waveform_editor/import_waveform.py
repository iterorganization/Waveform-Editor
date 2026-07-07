from collections import namedtuple

import numpy as np

from waveform_editor.base_waveform import BaseWaveform
from waveform_editor.import_resolver import INTERP_MODES

# One import within an ImportWaveform: which entry to read (ref) and how.
ImportSpec = namedtuple("ImportSpec", ["ref", "path", "time_offset", "interp"])


def _spec_from_entry(entry):
    interp = entry.get("user_interp", "closest")
    return ImportSpec(
        ref=entry.get("user_ref", ""),
        path=entry.get("user_path") or None,
        time_offset=entry.get("user_time_offset", 0.0) or 0.0,
        interp=interp if interp in INTERP_MODES else "closest",
    )


class ImportWaveform(BaseWaveform):
    """A waveform whose entire content is imported from external entries.

    Used for imports that cannot be expressed as a single analytic segment: non-0D
    quantities (a value per radial point, etc.) and wildcard paths (``.../*``) that
    mirror a whole subtree. This class only carries the imports' configuration; the
    exporter copies the (resampled) source into the target IDS via the ImportResolver.

    It may carry **several** imports (``[{ref: a}, {ref: b}]``), overlaid in listed
    order. A whole-IDS import (``<ids>/*``) is an overlay base for that IDS. Overlays
    are applied broadest-first (see :meth:`specificity`), so more specific imports win.
    """

    def __init__(self, entries, *, yaml_str="", name="waveform", dd_version=None):
        super().__init__(yaml_str, name, dd_version)
        self.yaml_str = yaml_str
        if isinstance(entries, dict):
            entries = [entries]
        self.specs = [_spec_from_entry(e) for e in entries]
        self.line_number = entries[0].get("line_number", 0) if entries else 0

    @property
    def specificity(self):
        """Concrete (pre-wildcard) path length. Broader overlays have a lower value and
        are applied first, so more specific imports win; ``*`` (whole entry) is 0."""
        segments = self.name.split("/")
        for i, segment in enumerate(segments):
            if segment == "*" or segment.endswith("(*)"):
                return i
        return len(segments)

    def get_value(
        self, time: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        # Imported, possibly non-scalar data is not plotted as a simple curve.
        if time is None:
            time = np.array([])
        return time, np.zeros_like(time, dtype=float)

    def get_yaml_string(self) -> str:
        return self.yaml_str
