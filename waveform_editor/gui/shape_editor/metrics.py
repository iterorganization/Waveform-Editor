import pandas as pd
import panel as pn
import param
from bokeh.models.widgets.tables import NumberFormatter
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.plasma_shape import GAP_SCALE
from waveform_editor.gui.util import card
from waveform_editor.settings import NiceSettings, settings


class Metrics(Viewer):
    """Table of the shape of the target and of the NICE result."""

    target = param.Dict(default={}, doc="The shape of the target, by metric [m]")
    result = param.Dict(default={}, doc="The shape of the NICE result, by metric [m]")
    machine_metrics = param.Dict(default={})
    nice_settings = param.ClassSelector(class_=NiceSettings)

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
        ELONGATION: ("κ", "", "Elongation"),
        TRIANGULARITY: ("δ", "", "Triangularity"),
        TRI_UPPER: ("δᵤ", "", "Triangularity upper"),
        TRI_LOWER: ("δₗ", "", "Triangularity lower"),
        Q95: ("q₉₅", "", "Edge safety factor"),
        MAJOR_RADIUS: ("R₀", "m", "Major radius"),
        VERTICAL: ("Z₀", "m", "Vertical position"),
        MINOR_RADIUS: ("a", "m", "Minor radius"),
    }

    def __init__(self, **params):
        super().__init__(nice_settings=settings.nice, **params)
        self._result = self._result_target = {}
        self._table = pn.widgets.Tabulator(
            disabled=True,
            show_index=False,
            margin=0,
            sortable=False,
            selectable=False,
            layout="fit_data_table",
            text_align="right",
            sizing_mode="stretch_width",
            stylesheets=[".tabulator-tableholder { overflow-y: hidden !important; }"],
        )
        self._update_table()

    @param.depends(
        "target", "result", "machine_metrics", "nice_settings.mode", watch=True
    )
    def _update_table(self):
        """A column per metric, with how far the result is from the target."""
        if self.result is not self._result:
            self._result, self._result_target = self.result, self.target
        metrics = {**self.METRICS, **self.machine_metrics}
        titles = {
            key: f"{symbol} [{unit}]" if unit else symbol
            for key, (symbol, unit, _) in metrics.items()
        }
        outdated = bool(self.result) and self.target != self._result_target
        table = pd.DataFrame(
            [self.target, self.result],
            index=["Target", "Result"],
            columns=list(metrics),
            dtype=float,  # a gap that could not be measured is None
        ) * [GAP_SCALE.get(unit, 1) for _, unit, _ in metrics.values()]
        table.loc["Difference"] = (
            float("nan") if outdated else table.loc["Result"] - table.loc["Target"]
        )
        if self.nice_settings.is_direct_mode:  # which has no target shape
            table = table.loc[["Result"]]
        value = table.rename(columns=titles).rename_axis("").reset_index()
        # Only the values change while the shape is edited, which is quicker to send
        if self._table.value is not None and list(self._table.value) == list(value):
            self._table.value = value
            return
        self._table.param.update(
            value=value,
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
            "Shape metrics",
            self._table,
            margin=(10, 0),
            css_classes=["metrics-card"],
        )
