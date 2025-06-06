from io import StringIO

import holoviews as hv
import panel as pn
import param
from holoviews import streams
from panel.viewable import Viewer
from ruamel.yaml import YAML

from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency
from waveform_editor.waveform import Waveform


class PlotterEdit(Viewer):
    """Class to plot a single waveform in edit mode."""

    plotted_waveform: Waveform = param.ClassSelector(class_=Waveform, allow_refs=True)

    def __init__(self, editor, **params):
        super().__init__(**params)
        self.editor = editor
        self.pane = pn.pane.HoloViews(sizing_mode="stretch_both")
        # TODO: The y axis should show the units of the plotted waveform
        self.xlabel = "Time (s)"
        self.ylabel = "Value"
        self.update_plot()

    @param.depends("plotted_waveform", watch=True)
    def update_plot(self):
        """
        Generate curves for each selected waveform and combine them into a Holoviews
        Overlay object, and update the plot pane.
        """
        overlay = self.plot_waveform(self.plotted_waveform)

        self.pane.object = overlay

    def plot_waveform(self, waveform):
        """
        Store the tendencies of a waveform into a holoviews overlay. If the waveform
        contains a piecewise linear tendency, enable the point draw tool.

        Args:
            waveform: The waveform to convert to a holoviews curve.

        Returns:
            A Holoviews Curve object.
        """

        if waveform is None or not waveform.tendencies:
            return hv.Curve(([], []), self.xlabel, self.ylabel)

        curves = []
        num_piecewise = 0
        for tendency in waveform.tendencies:
            times, values = tendency.get_value()
            curve = hv.Curve(
                (times, values), self.xlabel, self.ylabel, label=waveform.name
            )

            curve = curve.opts(
                line_width=2,
                framewise=True,
                show_legend=False,
                color=hv.Cycle("Category20").values[0],
            )
            if isinstance(tendency, PiecewiseLinearTendency):
                curve_stream = streams.CurveEdit(
                    data=curve.columns(),
                    source=curve,
                    style={"color": "black", "size": 10},
                )
                curve_stream.add_subscriber(
                    lambda data, idx=num_piecewise: self.piecewise_click_and_drag(
                        data, idx
                    )
                )
                num_piecewise += 1
            curves.append(curve)

        return hv.Overlay(curves)

    def piecewise_click_and_drag(self, piecewise_data, piecewise_idx):
        """Updates a piecewise linear tendency in the code editor YAML time/value data.
        Args:
            piecewise_data: Dictionary containing the new piecewise values.
            piecewise_idx: Index of the selected piecewise linear tendency.
        """
        yaml = YAML()
        content = self.editor.code_editor.value
        stream = StringIO(content)
        items = yaml.load(stream)

        piecewise_indices = [
            i for i, item in enumerate(items) if item.get("type") == "piecewise"
        ]

        if piecewise_idx >= len(piecewise_indices):
            return

        target_idx = piecewise_indices[piecewise_idx]
        items[target_idx]["time"] = [float(x) for x in piecewise_data[self.xlabel]]
        items[target_idx]["value"] = [float(y) for y in piecewise_data[self.ylabel]]

        output = StringIO()
        yaml.dump(items, output)
        self.editor.code_editor.value = output.getvalue()

    def __panel__(self):
        return pn.Column(self.pane)
