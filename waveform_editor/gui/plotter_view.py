import holoviews as hv
import param

from waveform_editor.gui.plotter_base import PlotterBase


class PlotterView(PlotterBase):
    """Class to plot multiple waveforms in view mode."""

    plotted_waveforms = param.Dict(default={})

    def __init__(self, **params):
        super().__init__(**params)
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
