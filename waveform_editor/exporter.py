import logging

import imas
import numpy as np
from imas.ids_path import IDSPath

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ConfigurationExporter:
    def __init__(self, times):
        self.times = times

    def to_ids(self, uri, waveform_map, dd_version=None, machine_description=None):
        """Export the waveforms in the configuration to IDSs.

        Args:
            uri: URI to the data entry.
            waveform_map: The waveform map of a WaveformConfiguration.
            dd_version: The data dictionary version to export to. If None, IMAS's
                default version will be used.
            machine_description: The machine description to copy and export the YAML to.
        """
        ids_map = self._get_ids_map(waveform_map)

        with imas.DBEntry(uri, "x", dd_version=dd_version) as entry:
            for ids_name, waveforms in ids_map.items():
                logger.info(f"Filling {ids_name}...")

                # Copy machine description if provided, otherwise start from empty IDS
                if machine_description:
                    with imas.DBEntry(
                        machine_description, "r", dd_version=dd_version
                    ) as entry_md:
                        ids = entry_md.get(ids_name)
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

    def _get_ids_map(self, waveform_map):
        """Constructs a mapping of IDS names to their corresponding waveform objects.

        Args:
            waveform_map: The waveform map of a WaveformConfiguration.

        Returns:
            A dictionary mapping IDS names to lists of waveform objects.
        """
        ids_map = {}
        for name, group in waveform_map.items():
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
        # We iterate through the waveforms in reverse order because they are typically
        # ordered with increasing indices. By processing them in reverse, we can resize
        # AoSs to their final size in a single step, avoiding repeated resizing.
        for waveform in reversed(waveforms):
            logger.info(f"Filling {waveform.name}...")
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
            _, values = waveform.get_value(self.times)
            self._fill_node_recursively(ids, path, values)

    def _fill_node_recursively(self, ids_node, path, values, *, part_idx=0):
        if part_idx >= len(path.parts):
            self._fill_values(ids_node, path, values)
            return

        self._traverse_node(ids_node, path, part_idx, values)

    def _traverse_node(self, ids_node, path, part_idx, values):
        part = path.parts[part_idx]
        index = path.indices[part_idx]
        current = ids_node[part]
        if index is not None:
            if isinstance(index, slice):
                self._traverse_slice(current, index, path, part_idx, values)
            else:
                if len(current) <= index:
                    current.resize(index + 1, keep=True)
                self._fill_node_recursively(
                    current[index], path, values, part_idx=part_idx + 1
                )
        elif (
            hasattr(current.metadata, "coordinate1")
            and current.metadata.coordinate1.is_time_coordinate
            and part != path.parts[-1]
        ):
            current.resize(len(self.times), keep=True)

            for i in range(len(self.times)):
                self._fill_node_recursively(
                    current[i], path, values[i], part_idx=part_idx + 1
                )
        else:
            self._fill_node_recursively(current, path, values, part_idx=part_idx + 1)

    def _fill_values(self, ids_node, path, values):
        if not hasattr(ids_node, "data_type"):
            raise ValueError(f"Waveform {path} is not a 'FLT_0D' or 'FLT_1D'.")

        if ids_node.data_type == "FLT_1D":
            ids_node.value = values
        elif ids_node.data_type == "FLT_0D":
            if not np.isscalar(values):
                raise ValueError(f"Expected scalar value for {path}, got: {values}")
            ids_node.value = values
        else:
            raise ValueError(f"{path} has unsupported data_type: {ids_node.data_type}.")

    def _traverse_slice(self, current, slice, path, part_idx, values):
        if slice.start is None and slice.stop is None:
            start = 0
            stop = len(current) or 1
        else:
            start = slice.start if slice.start is not None else 0
            stop = slice.stop if slice.stop is not None else len(current) or start + 1
        max_index = max(start, stop - 1)
        if len(current) <= max_index:
            current.resize(max_index + 1, keep=True)

        for i in range(start, stop):
            self._fill_node_recursively(current[i], path, values, part_idx=part_idx + 1)
