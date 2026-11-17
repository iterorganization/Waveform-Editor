import io
import logging
from contextlib import contextmanager

import imas
import numpy as np
from ruamel.yaml import YAML

from waveform_editor.config_entry import ConfigEntry
from waveform_editor.util import expand, has_slice

logger = logging.getLogger(__name__)


def _is_time_trace(metadata, name):
    """Whether a copy of ``name`` is one value per time step, so it can be plotted and
    used in expressions like any other waveform.
    """
    if metadata is None:
        return False
    has_trace_shape = metadata.ndim == 0 or (
        metadata.ndim == 1 and metadata.timebasepath
    )
    return bool(has_trace_shape and metadata.type.is_dynamic and not has_slice(name))


class CopyWaveform(ConfigEntry):
    """An entry whose value is taken from one of the configuration's imports."""

    def __init__(self, entry, *, config, yaml_str="", name="waveform"):
        self.dd_version = config.globals.dd_version
        super().__init__(yaml_str, name, self.dd_version)
        self.config = config
        # A name that is not a DD path has no IDS to read from: metadata is then None,
        # the copy is not a time trace, and the exporter skips it.
        self.ids_name, _, self.sub_path = name.partition("/")
        self.is_time_trace = _is_time_trace(self.metadata, name)
        self.line_number = entry.get("line_number", 0)
        self.ref = entry.get("user_copy", "")
        if not self.ref:
            self.annotations.add(self.line_number, "copy: must name an import.")
        elif self.uri is None:
            self.annotations.add(
                self.line_number,
                f"Unknown import {self.ref!r}.",
            )

    @property
    def uri(self):
        """The IMAS URI this copy reads from, or None if its import isn't declared."""
        return self.config.globals.imports.get(self.ref)

    @contextmanager
    def open(self):
        """Open the data entry this copy reads from, for the duration of the block."""
        with imas.DBEntry(self.uri, "r", dd_version=self.dd_version) as entry:
            yield entry

    def resampled(self, entry, time):
        """The source IDS resampled onto ``time``, taking the closest source time
        point to each entry."""

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

    def _read_trace(self, source):
        """This copy's values in ``source``, in time order. A path over a dynamic
        array of structure (``time_slice/.../ip``) yields one value per slice."""
        values = [node.value for node in expand(source, self.sub_path)]
        return np.asarray(values, dtype=float).ravel()

    def get_value(self, time: np.ndarray | None = None):
        empty_time = np.array([]) if time is None else time
        empty = (empty_time, np.zeros_like(empty_time, dtype=float))
        if self.uri is None or not self.is_time_trace:
            return empty
        if time is None:
            return self._native_curve(empty)
        if time.size == 0:
            return empty
        with self.open() as entry:
            values = self._read_trace(self.resampled(entry, time))
        if values.size == 1:
            # A time-independent source is broadcast across the export time base, so a
            # copy can be handed to the same code that handles analytic waveforms.
            values = np.full(len(time), float(values[0]))
        return time, values

    def _native_curve(self, empty):
        """The source's own ``(time, values)``, without resampling.

        Unlike an export, a plot must not break because an import is missing or its
        URI is wrong, so anything that goes wrong here is an empty curve.
        """
        try:
            with self.open() as entry:
                source = entry.get(self.ids_name)
                times = np.asarray(source.time, dtype=float)
                if times.size == 0:
                    return empty
                values = self._read_trace(source)
        except Exception:
            logger.debug("could not read %s from %r", self.name, self.ref)
            return empty
        return (times, values) if values.shape == times.shape else empty

    def get_yaml_string(self) -> str:
        if self.yaml is None:
            return ""
        stream = io.StringIO()
        YAML().dump(self.yaml, stream)
        return stream.getvalue()
