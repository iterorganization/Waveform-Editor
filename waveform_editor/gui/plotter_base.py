import holoviews as hv
import panel as pn
from panel.viewable import Viewer


class PlotterBase(Viewer):
    """Class to handle dynamic waveform plotting."""

    def __init__(self, **params):
        super().__init__(**params)
        self.pane = pn.pane.HoloViews(sizing_mode="stretch_both")
        self.plot_layout = pn.Column(self.pane)
        self.title = ""

    def plot_waveform(self, waveform, show_legend=True):
        """
        Store the tendencies of a waveform into a holoviews curve.

        Args:
            waveform: The waveform to convert to a holoviews curve.

        Returns:
            A Holoviews Curve object.
        """
        if waveform is None or not waveform.tendencies:
            return hv.Curve([])
        times, values = waveform.get_value()

        # TODO: The y axis should show the units of the plotted waveform
        line = hv.Curve((times, values), "Time (s)", "Value", label=waveform.name).opts(
            line_width=2, framewise=True, show_legend=show_legend
        )

        return line

    def __panel__(self):
        return self.plot_layout
