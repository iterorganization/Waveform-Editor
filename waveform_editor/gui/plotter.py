import holoviews as hv
import param

from waveform_editor.yaml_parser import YamlParser


class WaveformPlotter(param.Parameterized):
    """Class to handle dynamic waveform plotting."""

    selected_waveforms = param.Dict(default={})

    def __init__(self, **params):
        super().__init__(**params)
        self.yaml_parser = YamlParser()

    def plot_tendencies(self, waveform, label, plot_time_points=False):
        """
        Plot the tendencies of a waveform and return a holoviews curve.

        Args:
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

    def update_plot(self, selected_waveforms, width=1200, height=600):
        """
        Generate curves for each selected waveform and combine them into a Holoviews
        Overlay object.

        Args:
            selected_waveforms: dict containing all selected waveforms.

        Returns:
            An Holoviews overlay containing the curves
        """
        empty_overlay = hv.Overlay([hv.Curve([])]).opts(
            title="",
            show_legend=True,
            width=width,
            height=height,
        )

        if not selected_waveforms:
            return empty_overlay

        curves = []
        for name, waveform in selected_waveforms.items():
            plot = self.plot_tendencies(waveform, name)
            curves.append(plot)

        if curves:
            return hv.Overlay(curves).opts(
                title="", show_legend=True, width=width, height=height
            )

        return empty_overlay

    def get(self):
        return hv.DynamicMap(
            self.update_plot,
            streams=[self.param.selected_waveforms],
        )
