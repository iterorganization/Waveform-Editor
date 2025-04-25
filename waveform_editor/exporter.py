import logging

import imas
import numpy as np
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
        # We iterate through the waveforms in reverse order because they are typically
        # ordered with increasing indices. By processing them in reverse, we can resize
        # AoSs to their final size in a single step, avoiding repeated resizing.
        for waveform in reversed(waveforms):
            logger.info(f"Filling {waveform.name}...")
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
            _, values = waveform.get_value(self.times)
            self._fill_node_recursively(ids, path, values)

    def _fill_node_recursively(self, ids_node, path, values):
        """Recursively traverses the IDS node along the given path, and fills the
        values at the leaf node.

        Args:
            ids_node: The current IDS node.
            path: An IDSPath object.
            values: Values to set the IDS quantity values to.
        """
        if len(path.parts) == 0:
            self._fill_values(ids_node, values)
            return

        self._traverse_node(ids_node, path, values)

    def _traverse_path(self, path):
        """Removes the first path part from an IDSPath.

        For example:
            IDSPath("beam(2)/phase/angle") --> IDSPath("phase/angle")

        Args:
            path: The IDSPath to remove the first part from.

        Returns:
            The IDSPath without the first path part.
        """
        if len(path.parts) == 1:
            return IDSPath("")
        return IDSPath(str(path).split("/", 1)[1])

    def _traverse_node(self, ids_node, path, values):
        """Traverses an IDS node according to the current part of the path and handles
        indexing, slicing, and time coordinate expansion.

        Parameters:
            ids_node: The current IDS node.
            path: An IDSPath object.
            values: Values to set the IDS quantity values to.
        """
        part = path.parts[0]
        index = path.indices[0]
        current = ids_node[part]
        if index is not None:
            if isinstance(index, slice):
                self._traverse_slice(current, index, path, values)
            else:
                if len(current) <= index:
                    current.resize(index + 1, keep=True)
                self._fill_node_recursively(
                    current[index],
                    self._traverse_path(path),
                    values,
                )
        elif (
            hasattr(current.metadata, "coordinate1")
            and current.metadata.coordinate1.is_time_coordinate
            and part != path.parts[-1]
        ):
            current.resize(len(self.times), keep=True)

            for i in range(len(self.times)):
                self._fill_node_recursively(
                    current[i], self._traverse_path(path), values[i]
                )
        else:
            self._fill_node_recursively(current, self._traverse_path(path), values)

    def _fill_values(self, ids_node, values):
        """Sets values on a leaf node, ensuring data types match expectations.

        Parameters:
            ids_node: The IDS node to fill values into.
            values: The value(s) to assign.
        """
        # TODO: This error handling should be done when the waveforms are made,
        # instead of during the export.
        if not hasattr(ids_node, "data_type"):
            raise ValueError(
                f"{ids_node.metadata.name!r} is not a 'FLT_0D' or 'FLT_1D'."
            )

        if ids_node.data_type == "FLT_1D":
            if not ids_node.metadata.coordinate1.is_time_coordinate:
                raise ValueError(
                    f"{ids_node.metadata.name!r} is not a time-dependent quantity"
                )
            ids_node.value = values
        elif ids_node.data_type == "FLT_0D":
            # If the values are not split, the path does not contain a time dependent
            # node
            if not np.isscalar(values):
                raise ValueError(
                    f"{ids_node.metadata.name!r} is not a time-dependent quantity"
                )
            ids_node.value = values
        else:
            raise ValueError(
                f"{ids_node.metadata.name!r} has unsupported data_type: "
                f"{ids_node.data_type}."
            )

    def _traverse_slice(self, ids_node, slice, path, values):
        """Traverses sliced IDS nodes.

        Parameters:
            ids_node: The IDS node to traverse the slice of.
            slice: The slice object defining the range of indices.
            path: The IDSPath object.
            values: Values to set the IDS quantity values to.
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

        for i in range(start, stop):
            self._fill_node_recursively(ids_node[i], self._traverse_path(path), values)
