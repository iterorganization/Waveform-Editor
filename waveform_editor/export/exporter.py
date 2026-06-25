import logging
from pathlib import Path

import imas
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from imas.ids_path import IDSPath

from waveform_editor.export.pcssp_exporter import PCSSPExporter
from waveform_editor.ids_fill import fill_nodes
from waveform_editor.import_waveform import ImportWaveform
from waveform_editor.static_waveform import StaticWaveform

logger = logging.getLogger(__name__)


class ConfigurationExporter:
    def __init__(self, config, times, progress=None, received_idss=None):
        self.config = config
        self.times = times
        self.progress = progress
        # The resolver reads external data for {ref: ...} imports. received_idss are the
        # IDSs received over MUSCLE3 ports at run time (empty for a plain file export).
        self.resolver = config.ensure_resolver(received_idss or {})
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
            self._fill_waveforms(ids, waveforms)
            # Set the time mode after filling: a whole-IDS import may carry the time
            # mode of its (e.g. time-independent) source, which we override.
            # TODO: currently only IDSs with homogeneous time mode are supported
            ids.ids_properties.homogeneous_time = (
                imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
            )
            ids.time = self.times
            yield ids_name, ids

    def _get_ids_map(self):
        """Constructs a mapping of IDS names to their corresponding waveform objects.

        A root import (``*``) is bucketed into every IDS its sources provide, so it acts
        as a whole-IDS overlay base for each of them.

        Returns:
            A dictionary mapping IDS names to lists of waveform objects.
        """
        ids_map = {}
        for name, group in self.config.waveform_map.items():
            waveform = group[name]
            if isinstance(waveform, ImportWaveform) and waveform.is_root:
                provided = {
                    ids_name
                    for spec in waveform.specs
                    for ids_name in self.resolver.source_ids_names(spec.ref)
                }
                for ids_name in provided:
                    ids_map.setdefault(ids_name, []).append(waveform)
                continue
            # wildcard reference imports (e.g. .../profiles_1d/*) have no single DD node
            if "*" not in name and not waveform.metadata:
                logger.warning(
                    f"'{waveform.name}' does not exist in IDS, so it is not exported."
                )
                continue
            # Here we assume the first word of the waveform to contain the IDS name
            ids = waveform.name.split("/")[0]
            ids_map.setdefault(ids, []).append(waveform)
        return ids_map

    def _fill_waveforms(self, ids, waveforms):
        """Populates the given IDS object with waveform data.

        Args:
            ids: The IDS to populate with waveform data.
            waveforms: A list of waveform objects to be filled into the IDS.
        """
        # Structural imports (ImportWaveform) are overlaid first, broadest-first (a
        # stable sort keeps file order for equal specificity), so more specific imports
        # -- and then the explicit leaf waveforms below -- override them.
        imports = sorted(
            (w for w in waveforms if isinstance(w, ImportWaveform)),
            key=lambda w: w.specificity,
        )
        waveforms = [w for w in waveforms if not isinstance(w, ImportWaveform)]
        for waveform in imports:
            logger.debug(f"Importing {waveform.name}...")
            self._overlay_import(ids, waveform)
            self._increment_progress()

        self._fill_explicit(ids, waveforms)

    def _overlay_import(self, ids, waveform):
        """Overlay an ImportWaveform's source(s) onto ``ids``, in listed order.

        For a root (``*``) import, each source is copied as a whole-IDS overlay of this
        IDS (only the sources that actually provide it); otherwise the waveform's own
        path is the destination, with each spec's ``path`` overriding the source path.
        """
        ids_name = ids.metadata.name
        for spec in waveform.specs:
            if waveform.is_root:
                if ids_name not in self.resolver.source_ids_names(spec.ref):
                    continue
                src_path = dst_path = f"{ids_name}/*"
            else:
                src_path, dst_path = spec.path or waveform.name, waveform.name
            self.resolver.fill_import(
                ids,
                ref=spec.ref,
                src_path=src_path,
                dst_path=dst_path,
                time=self.times,
                time_offset=spec.time_offset,
                interp=spec.interp,
            )

    def _fill_explicit(self, ids, waveforms):
        """Fill the explicit (analytic / scalar-import / static) waveforms into ``ids``.

        Ensure get_value is only called once per waveform"""
        values_per_waveform = []

        # We iterate through the waveforms in reverse order because they are typically
        # ordered with increasing indices. By processing them in reverse, we avoid
        # unnecessary repeated resizing.
        for waveform in reversed(waveforms):
            logger.debug(f"Filling {waveform.name}...")
            path = IDSPath("/".join(waveform.name.split("/")[1:]))
            if isinstance(waveform, StaticWaveform):
                values = waveform.value  # a bare constant (e.g. an identifier name)
            else:
                # Scalar imports and analytic+import composites resolve themselves.
                _, values = waveform.get_value(self.times)
            values_per_waveform.append((path, values))
            fill_nodes(ids, path, values)
            self._increment_progress()

        # NOTE: We fill in two passes. The first pass (above) sizes every array of
        # structure; the second pass (below) re-fills once all are sized. This handles
        # e.g. 'beam(:)/phase/angle' processed before 'beam(4)/power_launched/data':
        # phase/angle must end up filled for all 4 beams. Some niche cases involving
        # multiple slices for different waveforms might still not be handled correctly.
        for waveform, (path, values) in zip(
            waveforms, values_per_waveform, strict=True
        ):
            logger.debug(f"Filling {waveform.name}...")
            fill_nodes(ids, path, values)
            self._increment_progress()

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

    def _increment_progress(self):
        """Increment the progress bar"""
        if self.progress:
            self.current_progress += 1
            # Maximum is is 90%, the last 10% must be set after exporting
            self.progress.value = int(90 * self.current_progress / self.total_progress)
