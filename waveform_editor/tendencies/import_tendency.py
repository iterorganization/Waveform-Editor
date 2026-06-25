import numpy as np
import param

from waveform_editor.import_resolver import INTERP_MODES
from waveform_editor.tendencies.base import BaseTendency


class ImportTendency(BaseTendency):
    """A waveform segment whose values are imported from an external entry.

    Instead of an analytic shape, the values are read from a named entry in
    ``globals.imports``. By default the same DD path the segment sits at is read
    (``default_path``, set by the parent waveform); ``path`` overrides it and
    ``time_offset`` shifts the sampling time. ``interp`` selects the resampling mode
    (closest/linear/previous) used when sampling onto the export time base.

    For a **0D (scalar)** quantity an import may be one segment among analytic ones,
    each filling its ``[start, end]`` window, so this is a real tendency. Non-0D
    quantities and wildcard paths instead use an
    :class:`~waveform_editor.import_waveform.ImportWaveform`.

    Values come from an :class:`~waveform_editor.import_resolver.ImportResolver` bound
    by the parent waveform: ``get_value(time)`` returns values resampled onto ``time``
    (export); ``get_value()`` returns the raw source samples (editing/plotting), clipped
    to this segment's window only when one was given.
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

    # Bound by the parent waveform before evaluation (see Waveform._bind_imports). Class
    # defaults so they exist while param watchers run during __init__ (before binding).
    resolver = None
    default_path = None

    @property
    def _path(self):
        return self.user_path or self.default_path

    @property
    def _has_window(self):
        """Whether the user gave an explicit time window (vs. spanning the source)."""
        return (
            self.user_start is not None
            or self.user_duration is not None
            or self.user_end is not None
        )

    def get_value(self, time: np.ndarray | None = None):
        if self.resolver is None or not self._path:
            # Unresolved (no config/resolver, or path unknown): placeholder curve so the
            # tendency interface stays satisfied for bounds/plotting.
            if time is None:
                time = np.array([self.start, self.end])
            return time, np.zeros(len(time))
        if time is None:
            # Editing/plotting: raw source samples, not resampled. Clipped to this
            # segment's [start, end] only when an explicit window was given.
            times, values = self.resolver.raw(
                self.user_ref, self._path, time_offset=self.user_time_offset
            )
            if not self._has_window:
                return times, values
            window = (times >= self.start) & (times <= self.end)
            return times[window], values[window]
        return time, self.resolver.sample(
            self.user_ref,
            self._path,
            time,
            time_offset=self.user_time_offset,
            interp=self.user_interp,
        )

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        return np.zeros(len(time))
