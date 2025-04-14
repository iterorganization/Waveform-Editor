import logging
import re

import imas
from imas.ids_struct_array import IDSStructArray

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
                try:
                    ids = entry.factory.new(ids_name)
                except imas.exception.IDSNameError:
                    logger.error(f"{ids_name} IDS does not exist.")
                    return
                # TODO: currently only IDSs with homogeneous time mode are supported
                ids.ids_properties.homogeneous_time = (
                    imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
                )
                ids.time = self.times
                self._fill_waveforms(ids, waveforms)
                entry.put(ids)

    def _get_ids_map(self):
        """Constructs a mapping of IDS names to their corresponding waveform objects.

        Returns:
            A dictionary mapping IDS names to lists of waveform objects.
        """
        ids_map = {}
        for name, group in self.config.waveform_map.items():
            waveform = group[name]
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
        # During the resizing of IDS nodes, data may be lost so first ensure all nodes
        # have the appropriate length to store the waveforms
        for waveform in waveforms:
            path = "/".join(waveform.name.split("/")[1:])
            try:
                self._ensure_path_exists(ids, path)
            except AttributeError:
                logger.error(
                    f"{path!r} path does not exist in {ids.metadata.name!r} IDS."
                )
                return

        for waveform in waveforms:
            logger.info(f"Filling {waveform.name}...")
            _, self.values = waveform.get_value(self.times)
            path = "/".join(waveform.name.split("/")[1:])
            if path in self.flt_0d_map:
                self._fill_flt_0d(ids, path)
            else:
                self._fill_flt_1d(ids, path)

    def _fill_flt_0d(self, ids, full_path):
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
            full_path: The full path to the FLT_0D quantity.
        """

        time_path = self.flt_0d_map[full_path]
        paths = [
            full_path.replace(time_path, f"{time_path}({i + 1})")
            for i in range(len(self.times))
        ]
        for i, path in enumerate(paths):
            if ids[path].data_type == "FLT_0D":
                ids[path] = self.values[i]
            else:
                raise ValueError(f"{ids[path].metadata.name} should be FLT_0D")

    def _fill_flt_1d(self, ids, path):
        """Fill a FLT_1D IDS quantity in an IDS.

        Arguments:
            ids: The IDS to fill.
            path: The path to the FLT_1D quantity to fill.
        """
        if hasattr(ids[path].metadata, "structure_reference"):
            struct_ref = ids[path].metadata.structure_reference
            if struct_ref == "signal_flt_1d":
                ids[path].data = self.values
            else:
                raise NotImplementedError(f"Structure {struct_ref} is not implemented.")
        else:
            if (
                not hasattr(ids[path].metadata, "coordinate1")
                or "time" not in str(ids[path].metadata.coordinate1)
                or ids[path].metadata.ndim != 1
            ):
                raise ValueError(f"{ids[path]} is not a 1D time-dependent quantity.")
            ids[path] = self.values

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
        path_list = path.split("/")
        current = ids
        for part in path_list:
            if "(" in part:
                match = re.search(r"\((\d+)\)", part)
                index = int(match.group(1))
                current = current[part.split("(")[0]]

                # We use 1-based indexing in the URI
                if len(current) < index:
                    current.resize(index)

                # Revert to 0-based indexing
                current = current[index - 1]
            else:
                # Ensure AoS have a non-zero length
                if isinstance(current, IDSStructArray) and len(current) == 0:
                    current.resize(1)
                    current = current[0]
                current = current[part]

        # If the quantity stores its time in another node, e.g. equilibrium/time_slice
        # Ensure that the length of this node matches the number of time steps
        time_path = current.metadata.path_doc
        if "itime" in time_path:
            time_path = time_path.split("(itime)")[0]
            ids[time_path].resize(len(self.times))
            # Map full path to coordinate time path
            self.flt_0d_map[path] = time_path
