import pandas as pd
import panel as pn
import param
from bokeh.models.widgets.tables import NumberFormatter
from panel.viewable import Viewer

from waveform_editor.gui.util import card


class Metrics(Viewer):
    """Table of the shape of the target and of the NICE result."""

    target = param.Dict(default={}, doc="The shape of the target, by metric")
    result = param.Dict(default={}, doc="The shape of the NICE result, by metric")
    machine_metrics = param.Dict(default={})

    ELONGATION = "elongation"
    TRIANGULARITY = "triangularity"
    TRI_UPPER = "tri_upper"
    TRI_LOWER = "tri_lower"
    Q95 = "q95"
    MAJOR_RADIUS = "r0"
    VERTICAL = "z0"
    MINOR_RADIUS = "a"

    # (symbol, unit, full name) - full name is shown as a hover tooltip
    METRICS = {
        ELONGATION: ("e", "", "Elongation"),
        TRIANGULARITY: ("t", "", "Triangularity"),
        TRI_UPPER: ("tᵤ", "", "Triangularity upper"),
        TRI_LOWER: ("tₗ", "", "Triangularity lower"),
        Q95: ("q₉₅", "", "Edge safety factor"),
        MAJOR_RADIUS: ("R₀", "m", "Major radius"),
        VERTICAL: ("Z₀", "m", "Vertical position"),
        MINOR_RADIUS: ("a", "m", "Minor radius"),
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._table = pn.widgets.Tabulator(
            disabled=True,
            show_index=False,
            margin=0,
            sortable=False,
            selectable=False,
            layout="fit_data_table",
            text_align="right",
            sizing_mode="stretch_width",
        )

    @param.depends("target", "result", "machine_metrics", watch=True)
    def _update_table(self):
        """A column per metric the target or result has, with how far apart they are."""
        metrics = {
            key: metadata
            for key, metadata in {**self.METRICS, **self.machine_metrics}.items()
            if key in self.target or key in self.result
        }
        titles = {
            key: f"{symbol} [{unit}]" if unit else symbol
            for key, (symbol, unit, _) in metrics.items()
        }
        difference = {
            key: self.result[key] - self.target[key]
            for key in self.target.keys() & self.result.keys()
        }
        table = pd.DataFrame(
            [self.target, self.result, difference],
            index=["Target", "Result", "Difference"],
            columns=list(metrics),
        )
        self._table.param.update(
            value=table.rename(columns=titles).rename_axis("").reset_index(),
            header_tooltips={
                titles[key]: name for key, (_, _, name) in metrics.items()
            },
            formatters={
                title: NumberFormatter(format="0.[000]", nan_format="—")
                for title in titles.values()
            },
        )

    def __panel__(self):
        return card(
            "Target vs result metrics",
            self._table,
            visible=self.param.target.rx.bool() | self.param.result.rx.bool(),
        )
