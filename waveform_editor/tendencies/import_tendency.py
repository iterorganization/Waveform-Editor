import numpy as np
import param

from waveform_editor.tendencies.base import BaseTendency

# User-facing interpolation modes -> IMAS interpolation constants (resolved by the
# exporter, which is the only place IMAS is imported).
INTERP_MODES = ("closest", "linear", "previous")


class ImportTendency(BaseTendency):
    """A waveform segment whose values are imported from an external entry.

    Instead of an analytic shape, the values are read from a named entry in
    ``globals.imports`` and resampled onto the export time base. By default the same DD
    path the segment sits at is read; ``path`` overrides it and ``time_offset`` shifts
    the sampling time. ``interp`` selects the resampling mode (closest/linear/previous).

    For a **0D (scalar)** quantity an import may be one segment among analytic ones
    (each fills its ``[start, end]`` window), so this is a real tendency. Non-0D
    quantities and wildcard paths cannot be combined this way -- those are represented
    by an :class:`~waveform_editor.import_waveform.ImportWaveform` instead.

    The read/resample needs IMAS and the export times, so it is performed by the
    exporter; this class carries the configuration of a single 0D import segment.
    """

    # User keys are passed with a ``user_`` prefix by the YAML parser.
    user_ref = param.String(
        default="", doc="Name of the entry in globals.imports to read."
    )
    user_time_offset = param.Number(
        default=0.0, doc="Offset added to the export time when sampling the import."
    )
    user_path = param.String(
        default=None,
        doc="DD path to read from the import (defaults to the waveform's path).",
    )
    user_interp = param.Selector(
        default="closest",
        objects=list(INTERP_MODES),
        doc="Interpolation mode used when resampling onto the export time base.",
    )

    def get_value(self, time: np.ndarray | None = None):
        # The exporter resolves import segments against the external entry; this
        # placeholder keeps the tendency interface satisfied for plotting/bounds.
        if time is None:
            time = np.array([self.start, self.end])
        return time, np.zeros(len(time))

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        return np.zeros(len(time))
