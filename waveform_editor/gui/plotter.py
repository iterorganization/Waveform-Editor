import holoviews as hv
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.yaml_parser import YamlParser


class WaveformPlotter(Viewer):
    """Class to handle dynamic waveform plotting."""

    plotted_waveforms = param.Dict(default={})

    def __init__(self, width=1200, height=600, **params):
        super().__init__(**params)
        self.width = width
        self.height = height
        self.yaml_parser = YamlParser()
        self.param.watch(self.update_plot, "plotted_waveforms")
        self.plot_layout = pn.Column(
            hv.Overlay([hv.Curve([])]).opts(
                title="",
                show_legend=True,
                width=self.width,
                height=self.height,
            )
        )

    def plot_tendencies(self, waveform, label, plot_time_points=False):
        """
        Store the tendencies of a waveform into a holoviews curve.

        Args:
            waveform: The waveform to convert to a holoviews curve.
            label: The label to add to the legend.
            plot_time_points: Whether to include markers for the data points.

        Returns:
            A Holoviews Curve object.
        """
        if not waveform.tendencies:
            return hv.Curve([])
        times, values = waveform.get_value()

        # TODO: The y axis should show the units of the plotted waveform
        line = hv.Curve((times, values), "Time (s)", "Value", label=label).opts(
            line_width=2, framewise=True, show_legend=True
        )

        if plot_time_points:
            points = hv.Scatter((times, values), "Time (s)", "Value").opts(
                size=5,
                color="red",
                marker="circle",
            )
            return line * points

        return line

    def update_plot(self, event):
        """
        Generate curves for each selected waveform and combine them into a Holoviews
        Overlay object.

        Args:
            plotted_waveforms: list containing waveforms to be plotted.

        Returns:
            An Holoviews overlay containing the curves
        """
        empty_overlay = hv.Overlay([hv.Curve([])]).opts(
            title="",
            show_legend=True,
            width=self.width,
            height=self.height,
        )

        if not self.plotted_waveforms:
            self.plot_layout[0] = empty_overlay
            return

        curves = []
        for waveform in self.plotted_waveforms.values():
            plot = self.plot_tendencies(waveform, waveform.name)
            curves.append(plot)

        if curves:
            self.plot_layout[0] = hv.Overlay(curves).opts(
                title="", show_legend=True, width=self.width, height=self.height
            )
        else:
            self.plot_layout[0] = empty_overlay

    def __panel__(self):
        return self.plot_layout
