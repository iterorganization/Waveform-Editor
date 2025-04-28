import logging
from pathlib import Path

import imas
import pandas as pd
import plotly.graph_objects as go
from imas.ids_path import IDSPath
from imas.ids_structure import IDSStructure

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ConfigurationExporter:
    def __init__(self, config, times):
        self.config = config
        self.times = times
        # We assume that all DD times are in seconds
        self.times_label = "Time [s]"

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
                logger.debug(f"Filling {ids_name}...")
                ids = entry.factory.new(ids_name)
                # TODO: currently only IDSs with homogeneous time mode are supported
                ids.ids_properties.homogeneous_time = (
                    imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
                )
                ids.time = self.times
                self._fill_waveforms(ids, waveforms)
                entry.put(ids)
        logger.info(f"Successfully exported waveform configuration to {uri}.")

    def to_png(self, dir_path):
        """Export the waveforms to PNGs.

        Args:
            dir_path: The directory path to store the PNGs into.
        """

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
        logger.info(f"Successfully exported waveform configuration PNGs to {dir_path}.")

    def to_csv(self, file_path):
        """Export the waveform to a CSV.

        Args:
            file_path: The file path to store the CSV to.
        """

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
            logger.debug(f"Filling {waveform.name}...")
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
            self._ensure_path_exists(ids, path)
            _, values = waveform.get_value(self.times)
            if path in self.flt_0d_map:
                self._fill_flt_0d(ids, path, values)
            else:
                self._fill_flt_1d(ids[path], values)

    def _fill_flt_0d(self, ids, path, values):
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
            values: The values to store in the IDS quantity.
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
            current.value = values[i]

    def _fill_flt_1d(self, quantity, values):
        """Fill a FLT_1D IDS quantity in an IDS.

        Arguments:
            quantity: The IDS quantity to fill.
        """
        if isinstance(quantity, IDSStructure) and hasattr(quantity, "data"):
            raise ValueError(
                f"Cannot export to '{quantity._path}' because it is an IDSStructure.\n"
                f"Did you mean to export to '{quantity._path}/data' instead?"
            )

        if (
            not quantity.metadata.coordinate1.is_time_coordinate
            or not quantity.data_type == "FLT_1D"
        ):
            raise ValueError(f"{quantity} is not a 1D time-dependent quantity.")

        quantity.value = values

    def _ensure_path_exists(self, ids, path, part_idx=0):
        """
        Recursively ensures that the full IDS path exists, resizing AoS as needed.
        Handles time-dependent paths by creating the full substructure for all time
        slices.

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
            values: The values to store in the IDS quantity.
            part_idx: index of current path part.
        """
        if part_idx >= len(path.parts):
            return

        part = path.parts[part_idx]
        index = path.indices[part_idx]
        current = ids[part]

        if index is not None:
            # TODO: Allow for slicing or all existing AoS,
            # e.g. slicing: ec_launchers/beam(1:24)/power_launched
            # e.g. all: ec_launchers/beam(:)/frequency
            if isinstance(index, slice):
                raise NotImplementedError("Slices are not yet implemented")
            if len(current) <= index:
                current.resize(index + 1, keep=True)
            self._ensure_path_exists(current[index], path, part_idx + 1)
        elif (
            hasattr(current.metadata, "coordinate1")
            and current.metadata.coordinate1.is_time_coordinate
            and part != path.parts[-1]
        ):
            current.resize(len(self.times), keep=True)
            self.flt_0d_map[path] = IDSPath(current._path)

            for i in range(len(self.times)):
                self._ensure_path_exists(current[i], path, part_idx + 1)
        else:
            self._ensure_path_exists(current, path, part_idx + 1)
