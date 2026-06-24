import logging
import re
from contextlib import contextmanager
from pathlib import Path

import imas
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from imas.ids_path import IDSPath
from imas.util import get_full_path, tree_iter

from waveform_editor.export.pcssp_exporter import PCSSPExporter
from waveform_editor.import_waveform import ImportWaveform
from waveform_editor.static_waveform import StaticWaveform
from waveform_editor.tendencies.import_tendency import ImportTendency

logger = logging.getLogger(__name__)


def _interp_const(mode):
    """Map a user interpolation mode name to an IMAS interpolation constant."""
    return {
        "closest": imas.ids_defs.CLOSEST_INTERP,
        "linear": imas.ids_defs.LINEAR_INTERP,
        "previous": imas.ids_defs.PREVIOUS_INTERP,
    }[mode]


class ConfigurationExporter:
    def __init__(self, config, times, progress=None, received_idss=None):
        self.config = config
        self.times = times
        self.progress = progress
        # {port_name: IDS} received over MUSCLE3 ports at run time. Imports whose source
        # is ``{port: <name>}`` read from this map instead of a URI.
        self.received_idss = received_idss or {}
        # external IDSs resampled onto the export times, keyed by
        # (source_key, ids, offset, interp)
        self._resample_cache = {}
        self.total_progress = None
        self.current_progress = None
        # We assume that all DD times are in seconds
        self.times_label = "Time [s]"
        # times must be None, or in increasing order
        if self.times is not None and not np.all(np.diff(self.times) > 0):
            raise ValueError("Time array must be in increasing order.")

    def to_pcssp_xml(self, file_path):
        """Export the configuration to a PCSSP XML file.

        Args:
            file_path: The file path to store the XML file to.
        """
        pcssp_exporter = PCSSPExporter(self.config, self.times)
        pcssp_exporter.export(file_path)
        logger.info(
            f"Successfully exported waveform configuration to PCSSP XML at {file_path}."
        )

    def to_ids(self, uri):
        """Export the waveforms in the configuration to IDSs.

        Args:
            uri: URI to the data entry.
        """
        with imas.DBEntry(uri, "x", dd_version=self.config.globals.dd_version) as entry:
            for _, ids in self._generate_idss(entry.factory):
                entry.put(ids)

        logger.info(f"Successfully exported waveform configuration to {uri}.")

    def to_ids_dict(self):
        """Export the waveforms in the configuration to IDSs.

        Returns:
            A dictionary with IDS names as keys and IDS objects as values.
        """
        factory = imas.IDSFactory(self.config.globals.dd_version)
        return {ids_name: ids for ids_name, ids in self._generate_idss(factory)}

    def _generate_idss(self, factory):
        """Generator for creating IDS objects from the configuration.
        Common logic for to_ids and to_ids_dict exporters.

        Args:
            factory: IDSFactory to use for creating new IDSs
        """
        ids_map = self._get_ids_map()
        self.total_progress = sum(2 * len(waveforms) for waveforms in ids_map.values())
        self.current_progress = 0
        for ids_name, waveforms in ids_map.items():
            logger.debug(f"Filling {ids_name}...")
            ids = factory.new(ids_name)
            self._fill_waveforms(ids, waveforms)
            # Set the time mode after filling: a whole-IDS import may carry the time
            # mode of its (e.g. time-independent) source, which we override.
            # TODO: currently only IDSs with homogeneous time mode are supported
            ids.ids_properties.homogeneous_time = (
                imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
            )
            ids.time = self.times
            yield ids_name, ids

    @staticmethod
    def _port_of(source):
        """The MUSCLE3 port name if ``source`` is a port-import, else None. A
        port-import is ``{port: <name>}`` or the ``port:<name>`` string shorthand."""
        if isinstance(source, dict) and "port" in source:
            return source["port"]
        if isinstance(source, str) and source.startswith("port:"):
            return source[len("port:") :]
        return None

    @contextmanager
    def _open_import(self, source):
        """Yield a DBEntry to read an import source from. ``source`` is an IMAS URI
        string, or a port-import referring to an IDS received over a MUSCLE3 port
        (loaded into an in-memory entry so it can be sliced like any other)."""
        dd = self.config.globals.dd_version
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

    def _resample_source(self, ids_name, source, time_offset, interp):
        """An external IDS resampled onto the export times (shifted by time_offset).

        The source is read in full and hosted in an in-memory entry so it can be
        resampled slice-by-slice via get_slice regardless of its backend (netCDF does
        not support get_slice directly). A time-independent source (e.g. a machine
        description) has no time dimension, so it is used as-is. Cached.
        """
        port = self._port_of(source)
        source_key = ("port", port) if port is not None else source
        key = (source_key, ids_name, time_offset, interp)
        if key not in self._resample_cache:
            dd = self.config.globals.dd_version
            with self._open_import(source) as ext:
                full = ext.get(ids_name)
            homogeneous = int(full.ids_properties.homogeneous_time) == (
                imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
            )
            if not homogeneous:
                self._resample_cache[key] = full
            else:
                interp_const = _interp_const(interp)
                with imas.DBEntry("imas:memory?path=/src", "w", dd_version=dd) as src:
                    src.put(full)
                    slices = [
                        src.get_slice(ids_name, float(t) + time_offset, interp_const)
                        for t in self.times
                    ]
                with imas.DBEntry("imas:memory?path=/dst", "w", dd_version=dd) as dst:
                    for sl in slices:
                        dst.put_slice(sl)
                    self._resample_cache[key] = dst.get(ids_name)
        return self._resample_cache[key]

    def _reference_values(self, waveform, tendency):
        """Values for a 0D import tendency: read its (resampled) source node from the
        named import. Defaults to the waveform's own DD path; the tendency's ``path``
        overrides it, ``time_offset`` shifts the sampling time and ``interp`` selects
        the resampling mode."""
        source = self.config.imports[tendency.user_ref]
        path = tendency.user_path or waveform.name
        ids_name, sub = path.split("/", 1)
        resampled = self._resample_source(
            ids_name, source, tendency.user_time_offset, tendency.user_interp
        )
        return self._extract_values(resampled, IDSPath(sub))

    def _composite_values(self, waveform):
        """Assemble a scalar waveform whose segments mix reference and analytic
        tendencies, masking each over its [start, end] window (later segments win at a
        shared boundary, as in the analytic evaluator). Reference segments read the
        external entry at the export times in their window. Scalar quantities only."""
        values = np.zeros(len(self.times))
        for tendency in waveform.tendencies:
            mask = (self.times >= tendency.start) & (self.times <= tendency.end)
            if not mask.any():
                continue
            if isinstance(tendency, ImportTendency):
                values[mask] = np.asarray(self._reference_values(waveform, tendency))[
                    mask
                ]
            else:
                _, segment = tendency.get_value(self.times[mask])
                values[mask] = segment
        return values

    def _fill_import_waveform(self, ids, waveform):
        """Fill an ImportWaveform: copy its (resampled) source into ``ids``.

        Index wildcards (``source(*)/...``) are expanded against the source, iterating
        over every element of that array of structure; a trailing ``/*`` mirror-copies a
        whole subtree; everything else copies a single node. The source path defaults to
        the waveform's own DD path; ``path`` overrides it, ``time_offset`` shifts the
        sampling time and ``interp`` the resampling mode.
        """
        source = self.config.imports[waveform.ref]
        src_ids, src_sub = (waveform.path or waveform.name).split("/", 1)
        _, dst_sub = waveform.name.split("/", 1)
        resampled = self._resample_source(
            src_ids, source, waveform.time_offset, waveform.interp
        )
        for csrc, cdst, is_subtree in self._expand_index_wildcards(
            resampled, src_sub, dst_sub
        ):
            if is_subtree:
                prefix = csrc.split("*", 1)[0].rstrip("/")
                subtree = self._navigate(resampled, IDSPath(prefix))
                for leaf in tree_iter(subtree, leaf_only=True, visit_empty=False):
                    self._mirror_leaf(resampled, ids, get_full_path(leaf))
            else:
                values = self._extract_values(resampled, IDSPath(csrc))
                self._fill_nodes_recursively(ids, IDSPath(cdst), values)

    def _expand_index_wildcards(self, root, src_sub, dst_sub):
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
            yield from self._expand_index_wildcards(
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
    def _navigate(node, path):
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

    def _extract_values(self, node, path, path_index=0):
        """Mirror of _fill_nodes_recursively: read the values at ``path`` from ``node``,
        as a per-time list where the path crosses a dynamic array of structures."""
        if path_index == len(path.parts):
            return node.value
        part = path.parts[path_index]
        index = path.indices[path_index]
        node = node[part]
        next_index = path_index + 1
        if index is None:
            if node.metadata.type.is_dynamic and part != path.parts[-1]:
                return [self._extract_values(item, path, next_index) for item in node]
            return self._extract_values(node, path, next_index)
        elif isinstance(index, slice):
            start, stop = self._resize_slice(node, index)
            return [
                self._extract_values(node[i], path, next_index)
                for i in range(start, stop)
            ]
        else:
            return self._extract_values(node[index], path, next_index)

    def to_png(self, dir_path):
        """Export the waveforms to PNGs.

        Args:
            dir_path: The directory path to store the PNGs into.
        """
        self.total_progress = len(self.config.waveform_map)
        self.current_progress = 0

        Path(dir_path).mkdir(parents=True, exist_ok=True)
        for name, group in self.config.waveform_map.items():
            waveform = group[name]
            times, values = waveform.get_value(self.times)
            ylabel = f"Value [{waveform.units}]"
            fig = go.Figure(data=go.Scatter(x=times, y=values, mode="lines"))
            fig.update_layout(
                title=waveform.name,
                xaxis_title=self.times_label,
                yaxis_title=ylabel,
                xaxis=dict(exponentformat="e", showexponent="all"),
                yaxis=dict(exponentformat="e", showexponent="all"),
            )
            output_path = dir_path / name.replace("/", "_")
            png_file = output_path.with_suffix(".png")
            logger.debug(f"Writing PNG: {png_file}...")
            fig.write_image(png_file, format="png")
            self._increment_progress()
        logger.info(f"Successfully exported waveform configuration PNGs to {dir_path}.")

    def to_csv(self, file_path):
        """Export the waveform to a CSV.

        Args:
            file_path: The file path to store the CSV to.
        """
        self.total_progress = len(self.config.waveform_map)
        self.current_progress = 0
        data = {"time": self.times}

        for name, group in self.config.waveform_map.items():
            logger.debug(f"Collecting data for {name}...")
            waveform = group[name]
            _, values = waveform.get_value(self.times)
            if len(values) != len(self.times):
                logger.warning(
                    f"{name} does not match the number of times, and is not exported."
                )
                continue
            data[name] = values
            self._increment_progress()

        df = pd.DataFrame(data)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(file_path, index=False)
        logger.info(f"Successfully exported waveform configuration to {file_path}.")

    def _get_ids_map(self):
        """Constructs a mapping of IDS names to their corresponding waveform objects.

        Returns:
            A dictionary mapping IDS names to lists of waveform objects.
        """
        ids_map = {}
        for name, group in self.config.waveform_map.items():
            waveform = group[name]
            # wildcard reference imports (e.g. .../profiles_1d/*) have no single DD node
            if "*" not in name and not waveform.metadata:
                logger.warning(
                    f"'{waveform.name}' does not exist in IDS, so it is not exported."
                )
                continue
            split_path = waveform.name.split("/")
            # Here we assume the first word of the waveform to contain the IDS name
            ids = split_path[0]
            ids_map.setdefault(ids, []).append(waveform)
        return ids_map

    def _fill_waveforms(self, ids, waveforms):
        """Populates the given IDS object with waveform data.

        Args:
            ids: The IDS to populate with waveform data.
            waveforms: A list of waveform objects to be filled into the IDS.
        """
        # Whole-subtree / non-0D imports (ImportWaveform) are copied straight from the
        # resampled source first, so explicit leaf waveforms below can override them.
        # A whole-IDS import (`<ids>/*`) thus acts as an overlay base.
        imports = [w for w in waveforms if isinstance(w, ImportWaveform)]
        waveforms = [w for w in waveforms if not isinstance(w, ImportWaveform)]
        for waveform in imports:
            logger.debug(f"Importing {waveform.name}...")
            self._fill_import_waveform(ids, waveform)
            self._increment_progress()

        # Ensure get_value is only called once per waveform
        values_per_waveform = []

        # We iterate through the waveforms in reverse order because they are typically
        # ordered with increasing indices. By processing them in reverse, we avoid
        # unnecessary repeated resizing.
        for waveform in reversed(waveforms):
            logger.debug(f"Filling {waveform.name}...")
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
            tendencies = waveform.tendencies
            has_ref = any(isinstance(t, ImportTendency) for t in tendencies)
            if isinstance(waveform, StaticWaveform):
                values = waveform.value  # a bare constant (e.g. an identifier name)
            elif has_ref and len(tendencies) == 1:
                values = self._reference_values(waveform, tendencies[0])
            elif has_ref:
                # mixed import + analytic segments: assemble per-time (scalars only)
                values = self._composite_values(waveform)
            else:
                _, values = waveform.get_value(self.times)
            values_per_waveform.append((path, values))
            self._fill_nodes_recursively(ids, path, values, fill=False)
            self._increment_progress()

        # NOTE: We perform two passes:
        # - The first pass (above) resizes the necessary nodes without filling values.
        # - The second pass (below) actually fills the nodes with their values.
        #
        # This two-pass process ensures correct handling of the following example, where
        # 'beam(:)/phase/angle' is processed before 'beam(4)/power_launched/data'.
        # Here, phase/angle should be filled for all 4 beams.
        # However, certain niche cases involving multiple slices for different waveforms
        # might still not be handled correctly.
        for waveform, (path, values) in zip(
            waveforms, values_per_waveform, strict=True
        ):
            logger.debug(f"Filling {waveform.name}...")
            self._fill_nodes_recursively(ids, path, values)
            self._increment_progress()

    def _increment_progress(self):
        """Increment the progress bar"""
        if self.progress:
            self.current_progress += 1
            # Maximum is is 90%, the last 10% must be set after exporting
            self.progress.value = int(90 * self.current_progress / self.total_progress)

    def _fill_nodes_recursively(self, node, path, values, path_index=0, fill=True):
        """Recursively fills nodes in the IDS based on the provided path and values.

        Args:
            node: The current IDS node.
            path: The path to the node, as an IDSPath object.
            values: The values to fill into the IDS node.
            path_index: The current index of the path we are processing.
            fill: Whether to fill the node with values.
        """
        if path_index == len(path.parts):
            if fill:
                node.value = values
            return
        part = path.parts[path_index]
        index = path.indices[path_index]

        node = node[part]
        next_index = path_index + 1
        if index is None:
            if node.metadata.type.is_dynamic and part != path.parts[-1]:
                if len(node) != len(values):
                    node.resize(len(values), keep=True)
                for item, value in zip(node, values, strict=True):
                    self._fill_nodes_recursively(item, path, value, next_index)
            else:
                self._fill_nodes_recursively(node, path, values, next_index)
        elif isinstance(index, slice):
            start, stop = self._resize_slice(node, index)
            for i in range(start, stop):
                self._fill_nodes_recursively(node[i], path, values, next_index)
        else:
            if len(node) <= index:
                node.resize(index + 1, keep=True)
            self._fill_nodes_recursively(node[index], path, values, next_index)

    def _resize_slice(self, ids_node, slice):
        """Resizes slice and returns the start/stop values of the slice

        Args:
            ids_node: The current IDS node to slice.
            slice: The slice for the IDS node.

        Returns:
            Tuple containing the start and stop values of the slice.
        """
        if slice.start is None and slice.stop is None:
            start = 0
            stop = len(ids_node) or 1
        else:
            start = slice.start if slice.start is not None else 0
            stop = slice.stop if slice.stop is not None else len(ids_node) or start + 1
        max_index = max(start, stop - 1)
        if len(ids_node) <= max_index:
            ids_node.resize(max_index + 1, keep=True)
        return start, stop
