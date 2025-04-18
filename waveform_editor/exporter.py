import logging

import imas
from imas.ids_path import IDSPath

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ConfigurationExporter:
    def __init__(self, config, times):
        self.config = config
        self.times = times

    def to_ids(self, uri, dd_version=None):
        """Export the waveforms in the configuration to IDSs.

        Args:
            uri: URI to the data entry.
            dd_version: The data dictionary version to export to. If None, IMAS's
                default version will be used.
        """
        ids_map = self._get_ids_map()
        with imas.DBEntry(uri, "x", dd_version=dd_version) as entry:
            for ids_name, waveforms in ids_map.items():
                logger.info(f"Filling {ids_name}...")
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
        self.flt_0d_map = {}
        # We iterate through the waveforms in reverse order because they are typically
        # ordered with increasing indices. By processing them in reverse, we can resize
        # AoSs to their final size in a single step, avoiding repeated resizing.
        for waveform in reversed(waveforms):
            logger.info(f"Filling {waveform.name}...")
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
            self._ensure_path_exists(ids, path)
            _, self.values = waveform.get_value(self.times)
            if path in self.flt_0d_map:
                self._fill_flt_0d(ids, path)
            else:
                self._fill_flt_1d(ids[path])

    def _fill_flt_0d(self, ids, path):
        """
        Fills a FLT_0D quantity in an IDS using time-dependent values.

        The base time path is stored in `self.flt_0d_map`. For each time step,
        the method constructs the full path with the appropriate time index and
        fills the corresponding FLT_0D value.

        Example:
            For full_path = "equilibrium/time_slice/boundary/elongation",
            the method fills for each time in self.times:
                - equilibrium/time_slice(1)/boundary/elongation
                - equilibrium/time_slice(2)/boundary/elongation
                - ...

        Args:
            ids: The IDS object to fill.
            path: The full path to the FLT_0D quantity.
        """

        # Fetch path to time dependent quantity
        time_path = self.flt_0d_map[path]
        len_time_path = len(time_path.parts)

        for i in range(len(self.times)):
            current = ids[time_path][i]
            # Traverse the remaining parts from the full path
            for part, index in list(path.items())[len_time_path:]:
                current = current[part]
                if index is not None:
                    current = current[index]
            if not current.data_type == "FLT_0D":
                raise ValueError(f"{current} is not a 0D time-dependent quantity.")
            current.value = self.values[i]

    def _fill_flt_1d(self, quantity):
        """Fill a FLT_1D IDS quantity in an IDS.

        Arguments:
            quantity: The IDS quantity to fill.
        """
        if hasattr(quantity.metadata, "structure_reference"):
            struct_ref = quantity.metadata.structure_reference
            if struct_ref == "signal_flt_1d":
                quantity.data = self.values
            else:
                raise NotImplementedError(
                    f"Exporting structure {struct_ref} is not implemented."
                )
        else:
            if (
                not quantity.metadata.coordinate1.is_time_coordinate
                or not quantity.data_type == "FLT_1D"
            ):
                raise ValueError(f"{quantity} is not a 1D time-dependent quantity.")
            quantity = self.values

    def _ensure_path_exists(self, ids, path):
        """
        Traverses a given path and modifies the AoS in the IDS to ensure the IDS
        quantity to be filled exists. Note that data may be lost during the resizing
        of a quantity.

        Examples:

        - ec_launchers/beam(123)/power_launched
          This will ensure ec_launchers.beam has a length of at least 123. Note, 1-based
          indexing is used in the URI.

        - equilibrium/time_slice/global_quantities/ip
          When the time coordinate is another AoS, this AoS is resized to ensure they
          can contain the exported time array, e.g.
          len(equilibrium.time_slice) == len(self.times)

        Args:
            ids: The IDS to export to.
            path: The path of the IDS quantity to export to.
        """
        current = ids
        for part, index in path.items():
            current = current[part]
            if index is not None:
                # TODO: Allow for slicing or all existing AoS,
                # e.g. slicing: ec_launchers/beam(1:24)/power_launched
                # e.g. all: ec_launchers/beam(:)/frequency
                if isinstance(index, slice):
                    raise NotImplementedError("Slices are not yet implemented")
                if len(current) <= index:
                    current.resize(index + 1, keep=True)
                current = current[index]
            elif (
                hasattr(current.metadata, "coordinate1")
                and current.metadata.coordinate1.is_time_coordinate
                and part != path.parts[-1]
            ):
                current.resize(len(self.times), keep=True)
                self.flt_0d_map[path] = IDSPath(current._path)
                current = current[0]
