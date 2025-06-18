import holoviews as hv
import panel as pn
import param
from panel.viewable import Viewer


class PlotterView(Viewer):
    """Class to plot multiple waveforms in view mode."""

    plotted_waveforms = param.Dict(default={})

    def __init__(self, **params):
        super().__init__(**params)
        self.pane = pn.pane.HoloViews(sizing_mode="stretch_both")
        self.update_plot()

    @param.depends("plotted_waveforms", watch=True)
    def update_plot(self):
        """
        Generate curves for each selected waveform and combine them into a Holoviews
        Overlay object, and update the plot pane.
        """
        curves = []
        for waveform in self.plotted_waveforms.values():
            curve = self.plot_waveform(waveform)
            curve = curve.opts(line_width=2, framewise=True, show_legend=True)
            curves.append(curve)

        if not curves:
            curves = [self.plot_waveform(None)]

        overlay = hv.Overlay(curves).opts(title="", show_legend=True)
        self.pane.object = overlay

    def plot_waveform(self, waveform):
        """
        Store the tendencies of a waveform into a holoviews curve.

        Args:
            waveform: The waveform to convert to a holoviews curve.

        Returns:
            A Holoviews Curve object.
        """
        # TODO: The y axis should show the units of the plotted waveform
        xlabel = "Time (s)"
        ylabel = "Value"

        if waveform is None or not waveform.tendencies:
            return hv.Curve(([], []), xlabel, ylabel)
        times, values = waveform.get_value()

        return hv.Curve((times, values), xlabel, ylabel, label=waveform.name)

    def __panel__(self):
        # Wrap HoloViews pane in Column to avoid update conflicts during rendering
        return pn.Column(self.pane)
