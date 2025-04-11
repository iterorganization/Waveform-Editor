import logging
import re

import imas

logger = logging.getLogger(__name__)


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
                ids = imas.IDSFactory().new(ids_name)
                # TODO: currently only homogeneous IDSs are supported
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
            splitted_path = waveform.name.split("/")
            ids = splitted_path[0]
            if ids not in ids_map:
                ids_map[ids] = []
            ids_map[ids].append(waveform)
        return ids_map

    def _fill_waveforms(self, ids, waveforms):
        """Populates the given IDS object with waveform data.

        Args:
            ids: The IDS to populate with waveform data.
            waveforms: A list of waveform objects to be filled into the IDS.
        """
        for waveform in waveforms:
            path = self._get_waveform_path(waveform)
            self._ensure_path_exists(ids, path)

        for waveform in waveforms:
            path = self._get_waveform_path(waveform)
            _, self.values = waveform.get_value(self.times)
            if "(:)" in path:
                self._fill_flt_0d(ids, path)
            else:
                self._fill_flt_1d(ids, path)

    def _get_waveform_path(self, waveform):
        """Helper method to extract path from waveform name."""
        return "/".join(waveform.name.split("/")[1:])

    def _fill_flt_0d(self, ids, path):
        """Fill a FLT_0D IDS quantity in an IDS.

        It is assumed that the time dependent AoS is provided in the path using `(:)`,
        for example:

        imas:hdf5?path=./test_equilibrium#equilibrium/time_slice(:)/boundary/elongation

        Arguments:
            ids: The IDS to fill.
            path: The path to the FLT_0D quantity to fill.
        """
        aos_path, remaining_path = path.split("(:)")
        aos_path = aos_path.strip("/")
        remaining_path = remaining_path.strip("/")
        aos = ids[aos_path]

        for i in range(len(self.times)):
            if aos[i][remaining_path].data_type == "FLT_0D":
                aos[i][remaining_path] = self.values[i]
            else:
                raise NotImplementedError("Should be float 0d")

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
                "time" not in str(ids[path].metadata.coordinate1)
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

        - imas:hdf5?path=./testdb#ec_launchers/beam(123)/power_launched
          This will ensure ec_launchers.beam has a length of at least 123. Note, 1-based
          indexing is used in the URI.

        - imas:hdf5?path=./testdb#equilibrium/time_slice(:)/boundary/elongation
          When '(:)' is encountered, it is assumed that this AoS should be the length of
          the exported time array, i.e. len(equilibrium.time_slice) == len(self.times)

        Args:
            ids: The IDS to export to.
            path: The path of the IDS quantity to export to.
        """
        path = path.strip("/")
        path_parts = path.split("/")
        current = ids
        for part in path_parts:
            if "(:)" in part:
                current = current[part.split("(")[0]]
                current.resize(len(self.times))
                current = current[0]

            elif "(" in part:
                match = re.search(r"\((\d+)\)", part)
                index = int(match.group(1))
                current = current[part.split("(")[0]]

                # We use 1-based indexing in the URI
                if len(current) < index:
                    current.resize(index)

                # Revert to 0-based indexing
                current = current[index - 1]
            else:
                current = current[part]
