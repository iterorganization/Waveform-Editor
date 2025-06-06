import param

from waveform_editor.gui.plotter_base import PlotterBase
from waveform_editor.waveform import Waveform


class PlotterEdit(PlotterBase):
    """Class to plot a single waveform in edit mode."""

    plotted_waveform: Waveform = param.ClassSelector(class_=Waveform, allow_refs=True)

    def __init__(self, **params):
        super().__init__(**params)
        self.update_plot()

    @param.depends("plotted_waveform", watch=True)
    def update_plot(self):
        """
        Generate curves for each selected waveform and combine them into a Holoviews
        Overlay object, and update the plot pane.
        """
        curve = self.plot_waveform(self.plotted_waveform)

        curve = curve.opts(
            line_width=2,
            framewise=True,
            show_legend=False,
        )

        self.pane.object = curve
