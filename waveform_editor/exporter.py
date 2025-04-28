import logging

import imas
from imas.ids_path import IDSPath

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ConfigurationExporter:
    def __init__(self, config, times):
        self.config = config
        self.times = times

    def to_ids(self, uri):
        """Export the waveforms in the configuration to IDSs.

        Args:
            uri: URI to the data entry.
        """
        ids_map = self._get_ids_map()

        with imas.DBEntry(uri, "x", dd_version=self.config.dd_version) as entry:
            for ids_name, waveforms in ids_map.items():
                logger.info(f"Filling {ids_name}...")

                # Copy machine description if provided, otherwise start from empty IDS
                if self.config.machine_description:
                    with imas.DBEntry(
                        self.config.machine_description,
                        "r",
                    ) as entry_md:
                        orig_ids = entry_md.get(ids_name, autoconvert=False)
                        ids = imas.convert_ids(orig_ids, self.config.dd_version)
                else:
                    ids = entry.factory.new(ids_name)
                # TODO: currently only IDSs with homogeneous time mode are supported
                ids.ids_properties.homogeneous_time = (
                    imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
                )
                ids.time = self.times
                self._fill_waveforms(ids, waveforms)
                entry.put(ids)
        logger.info(f"Successfully exported waveform configuration to {uri}.")

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
                    f"{waveform.name} does not exist in IDS, so it is not exported."
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
        # ordered with increasing indices. By processing them in reverse, we can resize
        # AoSs to their final size in a single step, avoiding repeated resizing.
        for waveform in reversed(waveforms):
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
            _, values = waveform.get_value(self.times)
            values_per_waveform.append((path, values))
            self._fill_nodes_recursively(ids, path, values, fill=False)

        # NOTE: We perform two passes:
        # - The first pass (above) resizes the necessary nodes without filling values.
        # - The second pass (below) actually fills the nodes with their values.
        #
        # This two-pass process ensures correct handling of the following example, where
        # 'beam(:)/phase/angle' is processed before 'beam(4)/power_launched/data'.
        # Here, phase/angle should be filled for all 4 beams.
        # However, certain niche cases involving multiple slices for different waveforms
        # might still not be handled correctly.
        for i, waveform in enumerate(waveforms):
            path, values = values_per_waveform[i]
            logger.debug(f"Filling {waveform.name}...")
            self._fill_nodes_recursively(ids, path, values)

    def _fill_nodes_recursively(self, node, path, values, path_index=0, fill=True):
        """Recursively fills nodes in the IDS based on the provided path and values.

        Args:
            node: The current IDS node.
            path: The path to the node, as an IDSPath object.
            values: The values to fill into the IDS node.
            path_index: The current index of the path we are processing.
            fill: Whether to fill the node with values.
        """
        next_index = path_index + 1
        if path_index == len(path.parts):
            if fill:
                node.value = values
            return
        part = path.parts[path_index]
        index = path.indices[path_index]

        node = node[part]
        if index is None:
            if (
                hasattr(node.metadata, "coordinate1")
                and node.metadata.coordinate1.is_time_coordinate
                and part != path.parts[-1]
            ):
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
