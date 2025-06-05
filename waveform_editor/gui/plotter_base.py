import holoviews as hv
import panel as pn
from panel.viewable import Viewer


class PlotterBase(Viewer):
    """Class to handle dynamic waveform plotting."""

    def __init__(self, **params):
        super().__init__(**params)
        self.pane = pn.pane.HoloViews(sizing_mode="stretch_both")

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
        return pn.Column(self.pane)
