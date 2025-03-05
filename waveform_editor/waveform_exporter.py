import csv
import logging

import imaspy
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


class WaveformExporter:
    def __init__(self, waveform, times):
        self.waveform = waveform
        self.times = times

        _, self.values = self.waveform.get_value(self.times)

        # TODO: introduce quantity types/units units from DD
        self.time_label = "Time [s]"
        self.value_label = "Value [unit]"

    def parse_uri(self, uri):
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

    def to_ids(self, uri, dd_version=None):
        uri_entry, uri_ids, occurrence, path = self.parse_uri(uri)
        entry = imaspy.DBEntry(uri_entry, "r", dd_version=dd_version)
        ids = entry.get(uri_ids, occurrence, autoconvert=False)

        if (
            ids.ids_properties.homogeneous_time
            == imaspy.ids_defs.IDS_TIME_MODE_HETEROGENEOUS
        ):
            is_homogeneous = False
        elif (
            ids.ids_properties.homogeneous_time
            == imaspy.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        ):
            is_homogeneous = True
            ids.time = self.times
        else:
            raise NotImplementedError(
                "The time mode must be homogeneous or heterogeneous."
            )

        if "()" in path:
            self._fill_flt_0d(ids, path, is_homogeneous)
        else:
            self._fill_flt_1d(ids, path, is_homogeneous)

        entry.put(ids)
        entry.close()

    def _fill_flt_0d(self, ids, path, is_homogeneous):
        aos_path, remaining_path = path.split("()")
        aos_path = aos_path.strip("/")
        remaining_path = remaining_path.strip("/")
        aos = ids[aos_path]
        aos.resize(len(self.times))

        for i, time in enumerate(self.times):
            if aos[i][remaining_path].data_type == "FLT_0D":
                aos[i][remaining_path] = self.values[i]
                if not is_homogeneous:
                    aos[i].time = time
            else:
                raise NotImplementedError("Should be float 0d")

    def _fill_flt_1d(self, ids, path, is_homogeneous):
        quantity = ids[path]
        struct_ref = quantity.metadata.structure_reference
        if struct_ref == "signal_flt_1d":
            quantity.data = self.values
            if not is_homogeneous:
                quantity.time = self.times
        else:
            raise NotImplementedError("Invalid data")

    def to_csv(self, file_path):
        with open(file_path, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([self.time_label, self.value_label])
            writer.writerows(zip(self.times, self.values))

    def to_png(self, file_path):
        """Export waveform data as a PNG plot using Plotly Express."""

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
