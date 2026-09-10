"""Reading values out of the data entries named in ``imports:``.

A configuration lists its external data as ``imports: {<name>: <IMAS URI>}``, and a
waveform takes its value from one of them with ``{copy: <name>}``. This module is the
only place that opens those entries: it reads each one once, resamples it onto the
export time base, and either returns the values (0D, so the waveform machinery can
treat a copy like any other per-time array) or writes them straight into the target IDS
(anything else -- a profile, a per-slice array).

Nothing here knows about MUSCLE3: a copy always comes from an entry on disk.
"""

import logging
import re
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import imas
import numpy as np
from imas.ids_path import IDSPath
from imas.ids_struct_array import IDSStructArray

from waveform_editor.ids_fill import fill_nodes, resize_slice

logger = logging.getLogger(__name__)

#: User-facing interpolation modes -> IMAS interpolation constants.
INTERP_MODES = ("closest", "linear", "previous")

#: A path segment: ``name``, ``name(2)`` or ``name(1:3)``.
_SEGMENT = re.compile(r"^([^()]+)(?:\((.*)\))?$")


def _has_slice(parts):
    """Whether any of these path segments carries a ``(a:b)`` slice."""
    return any(":" in (_SEGMENT.match(part).group(2) or "") for part in parts)


_INTERP_CONSTS = {
    "closest": imas.ids_defs.CLOSEST_INTERP,
    "linear": imas.ids_defs.LINEAR_INTERP,
    "previous": imas.ids_defs.PREVIOUS_INTERP,
}


class ImportReader:
    """Reads the entries named in ``imports:``.

    Args:
        imports: ``{name: IMAS URI}`` from the configuration.
        dd_version: DD version the configuration is written against; sources are
            converted to it on read.
        base_dir: Directory a relative ``path=`` in a URI is resolved against.
    """

    def __init__(self, imports, dd_version, base_dir=None):
        self.imports = imports or {}
        self.dd_version = dd_version
        self.base_dir = base_dir
        # Full source IDSs, keyed by (uri, ids_name): each entry is read once.
        self._cache = {}

    # -- source resolution ---------------------------------------------------

    def uri_of(self, ref):
        """The URI for import ``ref``, with a relative path made absolute."""
        if ref not in self.imports:
            raise KeyError(
                f"unknown import '{ref}': add it under imports:, or fix the name"
            )
        return self._absolute(self.imports[ref])

    def _absolute(self, uri):
        if self.base_dir is None or not isinstance(uri, str):
            return uri
        parsed = urlparse(uri)
        query = parse_qs(parsed.query)
        if "path" in query:
            path = Path(query["path"][0])
            if not path.is_absolute():
                query["path"] = [str(Path(self.base_dir, path).resolve())]
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query, doseq=True, safe="/"),
                parsed.fragment,
            )
        )

    @contextmanager
    def _open(self, uri):
        with imas.DBEntry(uri, "r", dd_version=self.dd_version) as entry:
            yield entry

    def _full(self, ref, ids_name):
        """The whole source IDS, read once and cached."""
        uri = self.uri_of(ref)
        key = (uri, ids_name)
        if key not in self._cache:
            logger.debug("reading %s from import '%s' (%s)", ids_name, ref, uri)
            with self._open(uri) as entry:
                self._cache[key] = entry.get(ids_name)
        return self._cache[key]

    @staticmethod
    def _is_homogeneous(ids):
        return int(ids.ids_properties.homogeneous_time) == (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )

    def _resampled(self, ref, ids_name, time, interp):
        """The source IDS resampled onto ``time``.

        A time-independent source (a machine description, say) has no time dimension
        and is returned unchanged. The source is hosted in an in-memory entry so it can
        be sliced with get_slice whatever backend it came from.
        """
        full = self._full(ref, ids_name)
        if not self._is_homogeneous(full) or np.asarray(full.time).size == 0:
            return full
        interp_const = _INTERP_CONSTS[interp]
        dd = self.dd_version
        with imas.DBEntry("imas:memory?path=/src", "w", dd_version=dd) as src:
            src.put(full)
            slices = [
                src.get_slice(ids_name, float(t), interp_const)
                for t in np.asarray(time)
            ]
        with imas.DBEntry("imas:memory?path=/dst", "w", dd_version=dd) as dst:
            for one_slice in slices:
                dst.put_slice(one_slice)
            return dst.get(ids_name)

    # -- reading -------------------------------------------------------------

    def raw(self, ref, ids_path):
        """The source's own ``(time, values)`` at ``ids_path``, without resampling.

        For plotting a copied waveform on the source's native time base. Returns empty
        arrays when the source has no time base, or the node is not one value per time.
        """
        ids_name, sub = ids_path.split("/", 1)
        full = self._full(ref, ids_name)
        times = np.asarray(full.time, dtype=float)
        if times.size == 0:
            return np.array([]), np.array([])
        values = np.asarray(self.extract(full, IDSPath(sub)), dtype=float)
        if values.shape != times.shape:
            return np.array([]), np.array([])
        return times, values

    def sample(self, ref, ids_path, time, interp="closest"):
        """0D values at ``ids_path``, resampled onto ``time``.

        A time-independent source value is broadcast across ``time``, so a copy can be
        handed to the same code that handles analytic waveforms.
        """
        ids_name, sub = ids_path.split("/", 1)
        resampled = self._resampled(ref, ids_name, time, interp)
        values = np.asarray(self.extract(resampled, IDSPath(sub)), dtype=float)
        if values.ndim == 0:
            values = np.full(len(time), float(values))
        return values

    def copy_into(self, ids, ref, src_path, dst_path, time, interp="closest"):
        """Copy the node at ``src_path`` from import ``ref`` into ``ids``.

        Used for everything a per-time array cannot express: profiles, per-slice
        arrays, and time-independent structure such as coil geometry. A slice
        (``coil(:)``) is expanded against the source, so each element is copied on its
        own -- one coil's data never lands on another's.
        """
        src_ids, src_sub = src_path.split("/", 1)
        _, dst_sub = dst_path.split("/", 1)
        resampled = self._resampled(ref, src_ids, time, interp)
        for one_src, one_dst in self.expand_slices(resampled, src_sub, dst_sub):
            values = self.extract(resampled, IDSPath(one_src))
            fill_nodes(ids, IDSPath(one_dst), values)

    def expand_slices(self, root, src_sub, dst_sub):
        """Expand every explicit slice in ``src_sub`` against the source.

        Yields concrete ``(src, dst)`` path pairs, with each ``name(a:b)`` replaced by
        the 1-based index of every element it covers. A dynamic array of structure
        addressed without an index (``time_slice/...``) is normally left alone: those
        are read and written as a value per time step. It is only made concrete when a
        slice further down has to be resolved inside each of its elements separately --
        ``source(:)/profiles_1d/ion(:)`` is a different ion array in every time slice,
        and they need not all be the same length.
        """
        src_parts = src_sub.split("/")
        dst_parts = dst_sub.split("/")

        for i, segment in enumerate(src_parts):
            name, index = _SEGMENT.match(segment).groups()
            if index is None:
                if not _has_slice(src_parts[i + 1 :]):
                    continue
                node = self.navigate(root, IDSPath("/".join(src_parts[:i] + [name])))
                if not isinstance(node, IDSStructArray):
                    continue
                indices = range(len(node))
            elif ":" in index:
                node = self.navigate(root, IDSPath("/".join(src_parts[:i] + [name])))
                low, _, high = index.partition(":")
                start = int(low) - 1 if low.strip() else 0
                stop = int(high) if high.strip() else len(node)
                indices = range(start, min(stop, len(node)))
            else:
                continue

            for k in indices:
                new_src = list(src_parts)
                new_dst = list(dst_parts)
                new_src[i] = f"{name}({k + 1})"
                if i < len(new_dst):
                    new_dst[i] = f"{name}({k + 1})"
                yield from self.expand_slices(
                    root, "/".join(new_src), "/".join(new_dst)
                )
            return

        yield src_sub, dst_sub

    # -- path helpers --------------------------------------------------------

    @staticmethod
    def navigate(root, path):
        """The node at ``path`` under ``root``."""
        node = root
        for part, index in zip(path.parts, path.indices, strict=True):
            node = node[part]
            if index is not None:
                node = node[index]
        return node

    def extract(self, node, path, path_index=0):
        """The value(s) at ``path``, as a per-element list wherever the path crosses an
        array of structure without a single index -- the mirror of
        :func:`~waveform_editor.ids_fill.fill_nodes`."""
        if path_index == len(path.parts):
            return node.value
        part = path.parts[path_index]
        index = path.indices[path_index]
        node = node[part]
        next_index = path_index + 1
        if index is None:
            if node.metadata.type.is_dynamic and part != path.parts[-1]:
                return [self.extract(item, path, next_index) for item in node]
            return self.extract(node, path, next_index)
        if isinstance(index, slice):
            start, stop = resize_slice(node, index)
            return [self.extract(node[i], path, next_index) for i in range(start, stop)]
        return self.extract(node[index], path, next_index)
