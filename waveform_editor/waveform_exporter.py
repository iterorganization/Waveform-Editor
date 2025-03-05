import csv
import logging

import numpy as np
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


class WaveformExporter:
    def __init__(self, waveform, times=None):
        self.waveform = waveform

        if not times:
            start = self.waveform.get_start()
            end = self.waveform.get_end()
            logger.warning(
                "No time array is provided, so using a linear interpolation with "
                "1000 points."
            )
            self.times = np.linspace(start, end, 1000)
        else:
            self.times = times

        _, self.values = self.waveform.get_value(self.times)

        # TODO: introduce quantity types/units units from DD
        self.time_label = "Time [s]"
        self.value_label = "Value [unit]"

    def to_ids(self, uri, path):
        # TODO:
        pass

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
