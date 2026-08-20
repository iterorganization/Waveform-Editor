import logging
import re
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import imas
import numpy as np
from imas.ids_path import IDSPath
from imas.util import get_full_path, tree_iter

from waveform_editor.ids_fill import fill_nodes, resize_slice

logger = logging.getLogger(__name__)

# User-facing interpolation modes -> IMAS interpolation constants.
INTERP_MODES = ("closest", "linear", "previous")


def _interp_const(mode):
    """Map a user interpolation mode name to an IMAS interpolation constant."""
    return {
        "closest": imas.ids_defs.CLOSEST_INTERP,
        "linear": imas.ids_defs.LINEAR_INTERP,
        "previous": imas.ids_defs.PREVIOUS_INTERP,
    }[mode]


class ImportResolver:
    """Reads named external data entries (``globals.imports``) from IMAS.

    This is the single place that opens external entries / MUSCLE3 port IDSs and turns
    them into values: the raw source samples (for editing/plotting) and values resampled
    onto a requested export time base (for export). The waveforms ask the resolver for
    their values; the exporter only writes the result into the target IDS.

    Each import name maps to an IMAS URI string, or a ``{port: <name>}`` referring to an
    IDS received on a MUSCLE3 port at run time (``received_idss``). Sources are read in
    full once and cached, then resampled in memory so any backend can be sliced
    (netCDF does not support get_slice directly).
    """

    def __init__(self, imports, dd_version, received_idss=None, base_dir=None):
        self.imports = imports or {}
        self.dd_version = dd_version
        # {port_name: IDS} received over MUSCLE3 ports at run time.
        self.received_idss = received_idss or {}
        self.base_dir = base_dir
        # full source IDSs, keyed by (source_key, ids_name)
        self._full_cache = {}

    # -- source resolution ----------------------------------------------------

    def _source(self, ref):
        """The import spec (URI string or ``{port: ...}``) for import name ``ref``."""
        if ref not in self.imports:
            raise KeyError(f"unknown import '{ref}'")
        return self._resolve_uri(self.imports[ref])

    def _resolve_uri(self, source):
        """Make a relative ``path=`` in an IMAS URI absolute, against ``base_dir``."""
        if self.base_dir is None or not isinstance(source, str):
            return source

        parsed = urlparse(source)
        query_params = parse_qs(parsed.query)

        if "path" in query_params:
            assert len(query_params["path"]) == 1
            rel_path = query_params["path"][0]
            abs_path = str(Path(self.base_dir, rel_path).resolve())
            query_params["path"] = [abs_path]

        new_query = urlencode(query_params, doseq=True, safe="/")

        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )

    @staticmethod
    def _port_of(source):
        """The MUSCLE3 port name if ``source`` is a port-import, else None. A
        port-import is ``{port: <name>}`` or the ``port:<name>`` string shorthand."""
        if isinstance(source, dict) and "port" in source:
            return source["port"]
        if isinstance(source, str) and source.startswith("port:"):
            return source[len("port:") :]
        return None

    def _source_key(self, source):
        port = self._port_of(source)
        return ("port", port) if port is not None else source

    @contextmanager
    def _open(self, source):
        """Yield a DBEntry to read an import source from. ``source`` is an IMAS URI
        string, or a port-import referring to an IDS received over a MUSCLE3 port
        (loaded into an in-memory entry so it can be sliced like any other)."""
        dd = self.dd_version
        port = self._port_of(source)
        if port is not None:
            ids = self.received_idss.get(port)
            if ids is None:
                raise KeyError(f"no IDS received on import port '{port}'")
            with imas.DBEntry("imas:memory?path=/", "w", dd_version=dd) as mem:
                mem.put(imas.convert_ids(ids, dd))
                yield mem
        else:
            with imas.DBEntry(source, "r", dd_version=dd) as ext:
                yield ext

    def _full(self, ids_name, source):
        """The full source IDS, read once and cached."""
        key = (self._source_key(source), ids_name)
        if key not in self._full_cache:
            with self._open(source) as ext:
                self._full_cache[key] = ext.get(ids_name)
        return self._full_cache[key]

    @staticmethod
    def _is_homogeneous(ids):
        return int(ids.ids_properties.homogeneous_time) == (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )

    def _resampled(self, ids_name, source, time, time_offset, interp):
        """The full source IDS resampled onto ``time`` (shifted by ``time_offset``).

        A time-independent source (e.g. a machine description) has no time dimension and
        is returned as-is. The source is hosted in an in-memory entry so it can be
        resampled slice-by-slice via get_slice regardless of its backend.
        """
        full = self._full(ids_name, source)
        if not self._is_homogeneous(full):
            return full
        dd = self.dd_version
        interp_const = _interp_const(interp)
        with imas.DBEntry("imas:memory?path=/src", "w", dd_version=dd) as src:
            src.put(full)
            slices = [
                src.get_slice(ids_name, float(t) + time_offset, interp_const)
                for t in time
            ]
        with imas.DBEntry("imas:memory?path=/dst", "w", dd_version=dd) as dst:
            for sl in slices:
                dst.put_slice(sl)
            return dst.get(ids_name)

    # -- public read API ------------------------------------------------------

    def raw(self, ref, ids_path, *, time_offset=0.0):
        """The source's own (time, values) at ``ids_path``, without resampling.

        Used for editing/plotting: the raw samples are shown on the source's native time
        base (mapped into waveform time by subtracting ``time_offset``). Returns empty
        arrays for a time-independent source, which has no curve to draw.
        """
        source = self._source(ref)
        ids_name, sub = ids_path.split("/", 1)
        full = self._full(ids_name, source)
        times = np.asarray(full.time, dtype=float)
        if times.size == 0:
            return np.array([]), np.array([])
        values = np.asarray(self.extract_values(full, IDSPath(sub)), dtype=float)
        if values.shape != times.shape:
            return np.array([]), np.array([])
        return times - time_offset, values

    def sample(self, ref, ids_path, time, *, time_offset=0.0, interp="closest"):
        """Values at ``ids_path`` from import ``ref``, resampled onto ``time``.

        Scalar quantities only; a static (time-independent) value is broadcast across
        ``time``. Non-0D quantities are handled structurally via :meth:`fill_import`.
        """
        source = self._source(ref)
        ids_name, sub = ids_path.split("/", 1)
        resampled = self._resampled(ids_name, source, time, time_offset, interp)
        values = np.asarray(self.extract_values(resampled, IDSPath(sub)), dtype=float)
        if values.ndim == 0:
            values = np.full(len(time), float(values))
        return values

    def fill_import(self, ids, *, ref, src_path, dst_path, time, time_offset, interp):
        """Copy a (resampled) non-0D / wildcard import from ``ref`` into ``ids``.

        Index wildcards (``source(*)/...``) are expanded against the source, iterating
        over every element of that array of structure; a trailing ``/*`` mirror-copies a
        whole subtree; everything else copies a single node.
        """
        source = self._source(ref)
        src_ids, src_sub = src_path.split("/", 1)
        _, dst_sub = dst_path.split("/", 1)
        resampled = self._resampled(src_ids, source, time, time_offset, interp)
        for csrc, cdst, is_subtree in self.expand_index_wildcards(
            resampled, src_sub, dst_sub
        ):
            if is_subtree:
                prefix = csrc.split("*", 1)[0].rstrip("/")
                subtree = self.navigate(resampled, IDSPath(prefix))
                for leaf in tree_iter(subtree, leaf_only=True, visit_empty=False):
                    self._mirror_leaf(resampled, ids, get_full_path(leaf))
            else:
                values = self.extract_values(resampled, IDSPath(csrc))
                fill_nodes(ids, IDSPath(cdst), values)

    # -- path / value helpers (read side) -------------------------------------

    def expand_index_wildcards(self, root, src_sub, dst_sub):
        """Expand every ``(*)`` index wildcard against the resampled source.

        Yields ``(concrete_src_sub, concrete_dst_sub, is_subtree)`` tuples: each ``(*)``
        is replaced (one at a time, recursively) by the 1-based index of every element
        of that array of structure in the source, a trailing ``/*`` is flagged as a
        whole-subtree mirror, and other index specs (``2``, ``2:3``, ``:``) pass through
        unchanged. The concrete paths are read/filled via IDSPath, which owns indexing.
        """
        src_parts = src_sub.split("/")
        dst_parts = dst_sub.split("/")

        star = next(
            (
                i
                for i, s in enumerate(src_parts)
                if s != "*" and self._parse_segment(s)[1] == "*"
            ),
            None,
        )
        if star is None:
            yield src_sub, dst_sub, src_parts[-1] == "*"  # trailing /* = subtree mirror
            return

        name = self._parse_segment(src_parts[star])[0]
        for k in range(1, self._count_aos(root, src_parts[:star], name) + 1):
            new_src = src_parts.copy()
            new_dst = dst_parts.copy()
            new_src[star] = f"{name}({k})"
            if star < len(new_dst):
                new_dst[star] = f"{name}({k})"
            yield from self.expand_index_wildcards(
                root, "/".join(new_src), "/".join(new_dst)
            )

    def _count_aos(self, root, prefix_parts, name):
        """The number of elements of the ``name`` array of structure in the source,
        reached by walking ``prefix_parts``. Explicit 1-based indices are honoured; an
        array of structure with no explicit index is descended into for every element.

        If ``name`` sits under a time-dependent array of structure, its element count
        must be the same in every slice -- a ``(*)`` wildcard cannot expand to a count
        that varies in time. A varying count raises rather than silently mis-populating.
        """
        counts = set()

        def walk(node, parts):
            if not parts:
                counts.add(len(node[name]))
                return
            seg_name, idx = self._parse_segment(parts[0])
            node = node[seg_name]
            if idx is not None and idx != ":" and ":" not in idx:
                walk(node[int(idx) - 1], parts[1:])  # explicit 1-based index
            elif hasattr(node, "resize"):  # array of structure: visit every element
                for element in node:
                    walk(element, parts[1:])
            else:  # plain structure
                walk(node, parts[1:])

        walk(root, prefix_parts)
        if len(counts) > 1:
            raise RuntimeError(
                f"cannot expand '{name}(*)': its element count varies across a "
                f"time-dependent parent (found {sorted(counts)}). An index wildcard "
                f"requires a uniform array-of-structure size."
            )
        return counts.pop() if counts else 0

    @staticmethod
    def _parse_segment(seg):
        """Split a path segment ``name`` or ``name(idx)`` into (name, idx-or-None)."""
        match = re.match(r"^([^()]+)(?:\((.*)\))?$", seg)
        return match.group(1), match.group(2)

    @staticmethod
    def navigate(node, path):
        """Walk an IDSPath, applying explicit indices; arrays of structure are kept."""
        for part, index in zip(path.parts, path.indices, strict=True):
            node = node[part]
            if index is not None:
                node = node[index]
        return node

    @staticmethod
    def _mirror_leaf(src_root, dst_root, full_path):
        """Copy one leaf, addressed by its concrete root path (e.g.
        ``source[0]/profiles_1d[3]/electrons/energy``), from src_root into dst_root,
        creating any intermediate arrays of structure on the way."""
        steps = [
            (m.group(1), int(m.group(2)) if m.group(2) else None)
            for m in re.finditer(r"([^/\[\]]+)(?:\[(\d+)\])?", full_path)
        ]
        src, dst = src_root, dst_root
        for name, index in steps[:-1]:
            src, dst = src[name], dst[name]
            if index is not None:
                if len(dst) <= index:
                    dst.resize(index + 1, keep=True)
                src, dst = src[index], dst[index]
        leaf_name = steps[-1][0]
        dst[leaf_name].value = src[leaf_name].value

    def extract_values(self, node, path, path_index=0):
        """Read the values at ``path`` from ``node`` as a per-time list where the path
        crosses a dynamic array of structures (mirror of the node-filling logic)."""
        if path_index == len(path.parts):
            return node.value
        part = path.parts[path_index]
        index = path.indices[path_index]
        node = node[part]
        next_index = path_index + 1
        if index is None:
            if node.metadata.type.is_dynamic and part != path.parts[-1]:
                return [self.extract_values(item, path, next_index) for item in node]
            return self.extract_values(node, path, next_index)
        elif isinstance(index, slice):
            start, stop = resize_slice(node, index)
            return [
                self.extract_values(node[i], path, next_index)
                for i in range(start, stop)
            ]
        else:
            return self.extract_values(node[index], path, next_index)
