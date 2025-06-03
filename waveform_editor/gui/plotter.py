from io import StringIO

import holoviews as hv
import panel as pn
import param
from holoviews import streams
from panel.viewable import Viewer
from ruamel.yaml import YAML

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

        num_piecewise = 0
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
                curve_stream.add_subscriber(
                    lambda data, idx=num_piecewise: self.click_and_drag(data, idx)
                )
                num_piecewise += 1
            curves.append(curve)

        # TODO: fix color
        overlay = hv.Overlay(curves).opts(
            title=self.title,
            show_legend=self.has_legend,
        )
        return overlay

    def click_and_drag(self, data, idx):
        yaml = YAML()
        content = self.main_gui.editor.code_editor.value
        stream = StringIO(content)
        items = yaml.load(stream)

        # Get indices for all piecewise tendencies
        piecewise_indices = [
            i for i, item in enumerate(items) if item.get("type") == "piecewise"
        ]

        if idx >= len(piecewise_indices):
            return

        target_idx = piecewise_indices[idx]
        items[target_idx]["time"] = [float(x) for x in data["x"]]
        items[target_idx]["value"] = [float(y) for y in data["y"]]

        output = StringIO()
        yaml.dump(items, output)
        self.main_gui.editor.code_editor.value = output.getvalue()

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
