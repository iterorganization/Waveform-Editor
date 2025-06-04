import holoviews as hv
import param

from waveform_editor.gui.plotter_base import PlotterBase
from waveform_editor.waveform import Waveform


class PlotterEdit(PlotterBase):
    """Class to plot a single waveform in edit mode."""

    plotted_waveform: Waveform = param.ClassSelector(class_=Waveform, allow_None=True)

    def __init__(self, **params):
        super().__init__(**params)
        self.param.watch(self.update_plot, "plotted_waveform")
        self.update_plot(None)

    def update_plot(self, event):
        """
        Generate curves for each selected waveform and combine them into a Holoviews
        Overlay object, and update the plot pane.
        """
        if self.plotted_waveform is None:
            curve = hv.Curve([])
        else:
            curve = self.plot_waveform(self.plotted_waveform, show_legend=False)

        self.pane.object = curve
