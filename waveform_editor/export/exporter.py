import logging
from pathlib import Path

import imas
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from imas.ids_path import IDSPath

from waveform_editor.copy_waveform import CopyWaveform
from waveform_editor.export.pcssp_exporter import PCSSPExporter
from waveform_editor.ids_fill import fill_nodes, size_arrays
from waveform_editor.waveform import ConstantWaveform

logger = logging.getLogger(__name__)


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

        Waveforms are written in the order they appear in the configuration, so where
        two of them write the same node the later one wins -- ``coil(:)`` followed by
        ``coil(4)`` means "every coil, except that one".

        Args:
            ids: The IDS to populate with waveform data.
            waveforms: A list of waveform objects to be filled into the IDS.
        """

        def is_structural(waveform):
            return isinstance(waveform, CopyWaveform) and waveform.is_structural

        # Evaluate every waveform once, before anything is written: sizing has to see
        # all the paths up front so that a ':' slice expands against the final array
        # sizes whatever order the waveforms appear in -- 'beam(:)/phase/angle'
        # followed by 'beam(4)/power_launched/data' still fills the angle of all four.
        values_per_waveform = []

        for waveform in waveforms:
            if is_structural(waveform):
                # A structural copy sizes and fills itself, from its own source.
                values_per_waveform.append(None)
                self._increment_progress()
                continue
            logger.debug(f"Sizing for {waveform.name}...")
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
            if (
                isinstance(waveform, ConstantWaveform)
                and not waveform.metadata.type.is_dynamic
            ):
                values = waveform.value
            else:
                _, values = waveform.get_value(self.times)
            values_per_waveform.append((path, values))
            self._increment_progress()

        size_arrays(
            ids,
            [item[0] for item in values_per_waveform if item is not None],
            len(self.times),
        )

        for waveform, precomputed in zip(waveforms, values_per_waveform, strict=True):
            if is_structural(waveform):
                logger.debug(f"Copying {waveform.name} from '{waveform.ref}'...")
                waveform.fill_into(ids, self.times, self.config.reader)
            else:
                logger.debug(f"Filling {waveform.name}...")
                path, values = precomputed
                fill_nodes(ids, path, values)
            self._increment_progress()

    def _increment_progress(self):
        """Increment the progress bar"""
        if self.progress:
            self.current_progress += 1
            # Maximum is is 90%, the last 10% must be set after exporting
            self.progress.value = int(90 * self.current_progress / self.total_progress)
