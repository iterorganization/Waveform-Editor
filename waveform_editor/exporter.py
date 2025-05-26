import logging
from pathlib import Path

import imas
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from imas.ids_path import IDSPath

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ConfigurationExporter:
    def __init__(self, config, times, progress=None):
        self.config = config
        self.times = times
        self.progress = progress
        self.total_progress = None
        self.current_progress = None
        # We assume that all DD times are in seconds
        self.times_label = "Time [s]"
        # times must be None, or in increasing order
        if self.times is not None and not np.all(np.diff(self.times) > 0):
            raise ValueError("Time array must be in increasing order.")

    def to_ids(self, uri):
        """Export the waveforms in the configuration to IDSs.

        Args:
            uri: URI to the data entry.
        """
        with imas.DBEntry(uri, "x", dd_version=self.config.dd_version) as entry:
            for _, ids in self._generate_idss(entry.factory):
                entry.put(ids)

        logger.info(f"Successfully exported waveform configuration to {uri}.")

    def to_ids_dict(self):
        """Export the waveforms in the configuration to IDSs.

        Returns:
            A dictionary with IDS names as keys and IDS objects as values.
        """
        factory = imas.IDSFactory(self.config.dd_version)
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

            # Copy machine description if provided, otherwise start from empty IDS
            md = self.config.machine_description.get(ids_name)
            if md:
                with imas.DBEntry(md, "r") as entry_md:
                    orig_ids = entry_md.get(ids_name, autoconvert=False)
                    ids = imas.convert_ids(orig_ids, self.config.dd_version)
            else:
                ids = factory.new(ids_name)
            # TODO: currently only IDSs with homogeneous time mode are supported
            ids.ids_properties.homogeneous_time = (
                imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
            )
            ids.time = self.times
            self._fill_waveforms(ids, waveforms)
            yield ids_name, ids

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
            if not waveform.metadata:
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
        # Ensure get_value is only called once per waveform
        values_per_waveform = []

        # We iterate through the waveforms in reverse order because they are typically
        # ordered with increasing indices. By processing them in reverse, we avoid
        # unnecessary repeated resizing.
        for waveform in reversed(waveforms):
            logger.debug(f"Filling {waveform.name}...")
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
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
        for waveform, (path, values) in zip(waveforms, values_per_waveform):
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
                for item, value in zip(node, values):
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
