import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.util import STYLES


class Metrics(Viewer):
    """Chips row showing equilibrium metrics below the flux map."""

    metrics = param.Dict(default={})

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
        self._pane = pn.pane.HTML(
            pn.bind(self._render, self.param.metrics),
            sizing_mode="stretch_width",
            stylesheets=STYLES,
        )

    def _render(self, metrics=None):
        chips = []
        for key, (symbol, unit, tooltip) in self.METRICS.items():
            val = metrics.get(key, "—") if metrics else "—"
            if isinstance(val, float):
                val = f"{val:.4g}"
            display = f"{val} {unit}".strip()
            chips.append(
                f'<span class="mc" title="{tooltip}">'
                f'<span class="mc-lbl">{symbol}</span>'
                f'<span class="mc-val">{display}</span>'
                f"</span>"
            )
        return '<div class="mc-wrap">' + "".join(chips) + "</div>"

    def __panel__(self):
        return self._pane
