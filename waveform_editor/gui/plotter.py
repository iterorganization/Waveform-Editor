import holoviews as hv
import panel as pn
import param
from holoviews import streams
from panel.viewable import Viewer

from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency


class WaveformPlotter(Viewer):
    """Class to handle dynamic waveform plotting."""

    plotted_waveforms = param.Dict(default={})

    def __init__(self, main_gui, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.pane = pn.pane.HoloViews(sizing_mode="stretch_both")
        self.plot_layout = pn.Column(self.pane)
        self.param.watch(self.update_plot, "plotted_waveforms")
        self.has_legend = True
        self.title = ""
        self.update_plot(None)

    def plot_tendencies(self, waveform, label):
        """
        Store the tendencies of a waveform into a holoviews curve.

        Args:
            waveform: The waveform to convert to a holoviews curve.
            label: The label to add to the legend.

        Returns:
            A Holoviews Curve object.
        """
        if not waveform.tendencies:
            return hv.Curve([])

        curves = []

        for tendency in waveform.tendencies:
            times, values = tendency.get_value()
            curve = hv.Curve((times, values), label=label).opts(
                line_width=2,
                framewise=True,
                show_legend=self.has_legend,
            )
            if self.main_gui.selector.edit_waveforms_enabled and isinstance(
                tendency, PiecewiseLinearTendency
            ):
                curve_stream = streams.CurveEdit(
                    data=curve.columns(),
                    source=curve,
                    style={"color": "black", "size": 10},
                )
                curve_stream.add_subscriber(self.click_and_drag)
            curves.append(curve)

        # TODO: fix color
        overlay = hv.Overlay(curves).opts(
            title=self.title,
            show_legend=self.has_legend,
        )
        return overlay

    def click_and_drag(self, data):
        code_lines = self.main_gui.editor.code_editor.value.strip().split("\n")
        updated_lines = []
        for line in code_lines:
            if "type: piecewise" in line:
                # Find the index of 'time: [' and 'value: [' in the line
                time_start = line.find("time: [")
                time_end = line.find("]", time_start) + 1
                value_start = line.find("value: [")
                value_end = line.find("]", value_start) + 1

                # Extract and replace time and value lists with new data
                new_time = ", ".join(str(x) for x in data["x"])
                new_value = ", ".join(str(y) for y in data["y"])
                new_line = (
                    line[:time_start]
                    + f"time: [{new_time}]"
                    + line[time_end:value_start]
                    + f"value: [{new_value}]"
                    + line[value_end:]
                )
                updated_lines.append(new_line)
            else:
                updated_lines.append(line)

        self.main_gui.editor.code_editor.value = "\n".join(updated_lines)

    def update_plot(self, event):
        """
        Generate curves for each selected waveform and combine them into a Holoviews
        Overlay object, and update the plot pane.
        """
        curves = hv.Curve([])
        for waveform in self.plotted_waveforms.values():
            curves *= self.plot_tendencies(waveform, waveform.name)
        # TODO: The y axis should show the units of the plotted waveform
        curves = curves.opts(title=self.title, xlabel="Time (s)", ylabel="Value")
        self.pane.object = curves

    def __panel__(self):
        return self.plot_layout
