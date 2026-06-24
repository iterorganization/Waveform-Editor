import numpy as np

from waveform_editor.base_waveform import BaseWaveform
from waveform_editor.tendencies.import_tendency import INTERP_MODES


class ImportWaveform(BaseWaveform):
    """A waveform whose entire content is imported from an external entry.

    Used for imports that cannot be expressed as a single analytic segment: non-0D
    quantities (a value per radial point, etc.) and wildcard paths (``.../*``) that
    mirror a whole subtree. The values are read from a named ``globals.imports`` entry
    and resampled onto the export time base by the exporter (which has IMAS and the
    export times); this class only carries the import's configuration.

    A whole-IDS import (``<ids>/*``) acts as an overlay base: it is applied before the
    other waveforms of that IDS, which then override individual leaves.
    """

    def __init__(self, entry, *, yaml_str="", name="waveform", dd_version=None):
        super().__init__(yaml_str, name, dd_version)
        self.yaml_str = yaml_str
        self.ref = entry.get("user_ref", "")
        self.path = entry.get("user_path") or None
        self.time_offset = entry.get("user_time_offset", 0.0) or 0.0
        interp = entry.get("user_interp", "closest")
        self.interp = interp if interp in INTERP_MODES else "closest"
        self.line_number = entry.get("line_number", 0)

    @property
    def is_wildcard(self):
        """Whether this import mirrors a whole subtree (its path contains ``*``)."""
        return "*" in (self.path or self.name)

    def get_value(
        self, time: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        # Imported, possibly non-scalar data is not plotted as a simple curve.
        if time is None:
            time = np.array([])
        return time, np.zeros_like(time, dtype=float)

    def get_yaml_string(self) -> str:
        return self.yaml_str
