import holoviews as hv
import panel as pn
import param
from panel.viewable import Viewer


class WaveformPlotter(Viewer):
    """Class to handle dynamic waveform plotting."""

    plotted_waveforms = param.Dict(default={})

    def __init__(self, **params):
        super().__init__(**params)
        self.pane = pn.pane.HoloViews(sizing_mode="stretch_both")
        self.plot_layout = pn.Column(self.pane)
        self.param.watch(self.update_plot, "plotted_waveforms")
        self.update_plot(None)

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
        Overlay object, and update the plot pane.
        """
        curves = [
            self.plot_tendencies(waveform, waveform.name)
            for waveform in self.plotted_waveforms.values()
        ]
        if not curves:
            # show an empty curve when there are no waveforms
            curves.append(hv.Curve([]))

        overlay = hv.Overlay(curves).opts(
            title="",
            show_legend=True,
        )
        self.pane.object = overlay

    def __panel__(self):
        return self.plot_layout
