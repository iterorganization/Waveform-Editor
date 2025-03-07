import csv
import logging
import re

import imas
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


class WaveformExporter:
    def __init__(self, waveform, times=None):
        self.waveform = waveform
        self.times, self.values = self.waveform.get_value(times)

        # TODO: introduce quantity types/units units from DD
        self.time_label = "Time [s]"
        self.value_label = "Value [unit]"

    def parse_uri(self, uri):
        """Parse URI into its constituents.

        Args:
            uri: String containing the URI.

        Returns:
            Constituents of the URI:
            - The scheme, backend and query parts of the URI
            - The name of the IDS.
            - The occurrence number (defaults to 0 if not provided)
            - Path of the IDS quantity to export to
        """
        uri_entry, fragment = uri.split("#")
        fragment_parts = fragment.split("/")
        idsname_part = fragment_parts[0]

        # Get occurrence number and IDS name
        if ":" in idsname_part:
            ids_name, occurrence_str = idsname_part.split(":")
            occurrence = int(occurrence_str)
        else:
            ids_name = idsname_part
            occurrence = 0

        ids_path = "/" + "/".join(fragment_parts[1:]) if len(fragment_parts) > 1 else ""
        return uri_entry, ids_name, occurrence, ids_path

    def to_ids(self, uri, dd_version=None, is_homogeneous=True):
        """Export the waveform to an IDS.

        Args:
            uri: URI containing scheme, backend, query and fragment parts.
            dd_version: The data dictionary version to export to. If None, IMASPy's
                default version will be used.
        """
        uri_entry, uri_ids, occurrence, path = self.parse_uri(uri)
        with imas.DBEntry(uri_entry, "x", dd_version=dd_version) as entry:
            ids = imas.IDSFactory().new(uri_ids)

            if is_homogeneous:
                ids.ids_properties.homogeneous_time = (
                    imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
                )
            else:
                ids.ids_properties.homogeneous_time = (
                    imas.ids_defs.IDS_TIME_MODE_HETEROGENEOUS
                )
            ids.time = self.times

            self._ensure_path_exists(ids, path)

            if "()" in path:
                self._fill_flt_0d(ids, path, is_homogeneous)
            else:
                self._fill_flt_1d(ids, path, is_homogeneous)

            entry.put(ids, occurrence)

    def to_csv(self, file_path):
        """Export the waveform to a CSV.

        Args:
            file_path: The file path and name to store the CSV to.
        """
        with open(file_path, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([self.time_label, self.value_label])
            writer.writerows(zip(self.times, self.values))

    def to_png(self, file_path):
        """Export the waveform to a PNG.

        Args:
            file_path: The file path and name to store the PNG to.
        """

        fig = go.Figure(
            data=go.Scatter(
                x=self.times,
                y=self.values,
            )
        )
        fig.update_layout(
            title="Waveform Plot",
            xaxis_title=self.time_label,
            yaxis_title=self.value_label,
        )
        fig.write_image(file_path, format="png")

    # TODO: implement export to XML format
    # def to_pcssp(self, file_path)
    #     pass

    def _fill_flt_0d(self, ids, path, is_homogeneous):
        """Fill a FLT_0D IDS quantity in an IDS.

        It is assumed that the time dependent AoS is provided in the path using `()`,
        for example:

        imas:hdf5?path=./test_equilibrium#equilibrium/time_slice()/boundary/elongation

        Arguments:
            ids: The IDS to fill.
            path: The path to the FLT_0D quantity to fill.
            is_homogeneous: Whether to fill the local time array, or the ids.time array
        """
        aos_path, remaining_path = path.split("()")
        aos_path = aos_path.strip("/")
        remaining_path = remaining_path.strip("/")
        aos = ids[aos_path]

        for i, time in enumerate(self.times):
            if aos[i][remaining_path].data_type == "FLT_0D":
                aos[i][remaining_path] = self.values[i]
                if not is_homogeneous:
                    aos[i].time = time
            else:
                raise NotImplementedError("Should be float 0d")

    def _fill_flt_1d(self, ids, path, is_homogeneous):
        """Fill a FLT_1D IDS quantity in an IDS.

        Arguments:
            ids: The IDS to fill.
            path: The path to the FLT_1D quantity to fill.
            is_homogeneous: Whether to fill the local time array, or the ids.time array
        """
        quantity = ids[path]
        struct_ref = quantity.metadata.structure_reference
        if struct_ref == "signal_flt_1d":
            quantity.data = self.values
            if not is_homogeneous:
                quantity.time = self.times
        else:
            raise NotImplementedError("Invalid data")

    def _ensure_path_exists(self, ids, path):
        """
        Traverses a given path and modifies the AoS in the IDS to ensure the IDS
        quantity to be filled exists.

        Examples:

        - imas:hdf5?path=./testdb#ec_launchers/beam(123)/power_launched
          This will ensure ec_launchers.beam has a length of at least 123. Note, 1-based
          indexing is used in the URI.

        - imas:hdf5?path=./testdb#equilibrium/time_slice()/boundary/elongation
          When '()' is encountered, it is assumed that this AoS should be the length of
          the exported time array, i.e. len(equilibrium.time_slice) == len(self.times)

        Args:
            ids: The IDS to export to.
            path: The path of the IDS quantity to export to.

        Returns:
            None. Modifies the `ids` structure in place.
        """
        path = path.strip("/")
        path_parts = path.split("/")
        current = ids
        for part in path_parts:
            if "()" in part:
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
