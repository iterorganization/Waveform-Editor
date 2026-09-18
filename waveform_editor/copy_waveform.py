import io
import logging
from contextlib import contextmanager

import imas
import numpy as np
from imas.ids_path import IDSPath
from ruamel.yaml import YAML

from waveform_editor.config_entry import ConfigEntry
from waveform_editor.ids_fill import expand_slices, extract, fill_nodes, has_slice

logger = logging.getLogger(__name__)


class CopyWaveform(ConfigEntry):
    """An entry whose value is taken from one of the configuration's imports.

    ``{copy: scenario}`` reads this waveform's own DD path from the ``scenario``
    import; ``path:`` reads a different one, which is what a waveform whose name is
    not a DD path needs.

    The source entry is only opened when the value is actually needed: once per
    export (the exporter opens each import for the duration of the export and hands
    the entry to :meth:`fill_into`), or on the spot when a single copy is plotted.
    """

    def __init__(
        self, entry, *, yaml_str="", name="waveform", config=None, dd_version=None
    ):
        super().__init__(yaml_str, name, dd_version)
        self.config = config
        self.dd_version = dd_version
        self.line_number = entry.get("line_number", 0)
        self.ref = entry.get("user_copy", "")
        self.path = entry.get("user_path") or None
        if not self.ref:
            self.annotations.add(self.line_number, "copy: must name an import.")
        elif self.uri is None:
            declared = ", ".join(sorted(self._imports)) or "<none>"
            self.annotations.add(
                self.line_number,
                f"Unknown import {self.ref!r}. Declared imports: {declared}.",
            )

    @property
    def _imports(self):
        return self.config.globals.imports if self.config else {}

    @property
    def uri(self):
        """The IMAS URI this copy reads from, or None if its import isn't declared."""
        return self._imports.get(self.ref)

    @property
    def source_path(self):
        """The DD path read from the source: ``path:`` if given, else our own name."""
        return self.path or self.name

    @property
    def ids_name(self):
        """The IDS this copy reads from."""
        return self.source_path.split("/", 1)[0]

    @contextmanager
    def open(self):
        """Open the data entry this copy reads from, for the duration of the block."""
        with imas.DBEntry(self.uri, "r", dd_version=self.dd_version) as entry:
            yield entry

    @property
    def is_time_trace(self):
        """Whether this copy is one value per time step, so it can be plotted and used
        in expressions like any other waveform."""
        if self.metadata is None:
            return self.path is not None
        has_trace_shape = self.metadata.ndim == 0 or (
            self.metadata.ndim == 1 and self.metadata.timebasepath
        )
        if not (has_trace_shape and self.metadata.type.is_dynamic):
            return False
        return not has_slice(self.name.split("/")) and not has_slice(
            self.source_path.split("/")
        )

    def _resampled(self, entry, time):
        """The source IDS resampled onto ``time``, taking the closest source time
        point to each entry.

        A time-independent source (a machine description, say) has no time dimension
        and is returned unchanged. The source is hosted in an in-memory entry so it
        can be sliced with get_slice whatever backend it came from.
        """
        full = entry.get(self.ids_name)
        homogeneous = int(full.ids_properties.homogeneous_time) == (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )
        if not homogeneous or np.asarray(full.time).size == 0:
            return full
        dd = self.dd_version
        with imas.DBEntry("imas:memory?path=/src", "w", dd_version=dd) as src:
            src.put(full)
            slices = [
                src.get_slice(self.ids_name, float(t), imas.ids_defs.CLOSEST_INTERP)
                for t in np.asarray(time)
            ]
        with imas.DBEntry("imas:memory?path=/dst", "w", dd_version=dd) as dst:
            for one_slice in slices:
                dst.put_slice(one_slice)
            return dst.get(self.ids_name)

    @property
    def _sub_path(self):
        return IDSPath(self.source_path.split("/", 1)[1])

    def get_value(self, time: np.ndarray | None = None):
        """One value per time for a 0D copy; an empty curve for anything else.

        Opens the source entry itself, so a copy can be evaluated anywhere a waveform
        can (a derived expression, a plot) without the caller knowing it reads a file.
        """
        if time is None:
            time = np.array([])
        if self.uri is None or not self.is_time_trace or time.size == 0:
            return time, np.zeros_like(time, dtype=float)
        with self.open() as entry:
            resampled = self._resampled(entry, time)
        values = np.asarray(extract(resampled, self._sub_path), dtype=float)
        if values.ndim == 0:
            # A time-independent source is broadcast across the export time base, so a
            # copy can be handed to the same code that handles analytic waveforms.
            values = np.full(len(time), float(values))
        return time, values

    def read_curve(self):
        """The source's own ``(time, values)``, without resampling -- for plotting a
        copy on the import's native time base.

        Empty when the import is undeclared, the source has no time base, or the node
        is not one value per time.
        """
        empty = (np.array([]), np.array([]))
        if self.uri is None or not self.is_time_trace:
            return empty
        try:
            with self.open() as entry:
                full = entry.get(self.ids_name)
                times = np.asarray(full.time, dtype=float)
                if times.size == 0:
                    return empty
                values = np.asarray(extract(full, self._sub_path), dtype=float)
        except Exception:
            logger.debug("could not read %s from %r", self.source_path, self.ref)
            return empty
        return (times, values) if values.shape == times.shape else empty

    def fill_into(self, ids, time, entry):
        """Copy this waveform's source node into ``ids``, reading from an already-open
        ``entry``.

        Used for everything a per-time array cannot express: profiles, per-slice
        arrays, and time-independent structure such as coil geometry. A slice
        (``coil(:)``) is expanded against the source, so each element is copied on its
        own -- one coil's data never lands on another's.
        """
        resampled = self._resampled(entry, time)
        src_sub = self.source_path.split("/", 1)[1]
        dst_sub = self.name.split("/", 1)[1]
        for one_src, one_dst in expand_slices(resampled, src_sub, dst_sub):
            values = extract(resampled, IDSPath(one_src))
            fill_nodes(ids, IDSPath(one_dst), values)

    def get_yaml_string(self) -> str:
        if self.yaml is None:
            return ""
        stream = io.StringIO()
        YAML().dump(self.yaml, stream)
        return stream.getvalue()
