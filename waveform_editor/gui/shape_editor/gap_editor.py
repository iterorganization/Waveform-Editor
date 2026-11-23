"""Editing the target shape through its gaps."""

import numpy as np
import panel as pn
from panel.viewable import Viewer

from waveform_editor.gui.util import INPUT_WIDTH, FormattedEditableFloatSlider
from waveform_editor.settings import settings
from waveform_editor.shape_editor.gaps import MACHINE_GAPS
from waveform_editor.shape_editor.plasma_shape_calc import (
    compute_outline_from_params,
    x_points_from_params,
)

# Gaps are shown in their unit, converted from metres
GAP_SCALE = {"m": 1, "cm": 100}


class GapEditor(Viewer):
    """A slider for each gap of the parameterized shape, to which it is fitted."""

    def __init__(self, shape_params):
        super().__init__()
        self.shape_params = shape_params
        self.nice_settings = settings.nice
        self._sliders = {}
        self.sliders = pn.FlexBox(margin=0)
        self.panel = pn.Column(
            shape_params.second_x_point_input(), self.sliders, margin=0
        )

    @property
    def gap_params(self):
        """The shape parameters fitted to the gaps. A double null takes its shape
        from its upper x-point instead of its elongation and triangularity."""
        if self.shape_params.second_x_point:
            return ("a", "center_r", "center_z", "rx", "zx", "rx_upper", "zx_upper")
        return self.shape_params.FIT_PARAMS

    def _shape_gaps(self, gaps, arguments):
        """The gaps of a parameterized shape, in metres by name."""
        r, z = compute_outline_from_params(**arguments)
        x_points = x_points_from_params(arguments)
        return gaps.compute_gaps(r, z, **gaps.shape_inputs(x_points))

    def create_sliders(self):
        """A slider for each gap the parameterized shape can be measured on, starting
        at the gap of the current shape."""
        gaps = MACHINE_GAPS.get(self.nice_settings.machine_preset)
        self._sliders = {}
        if gaps is None:
            self.sliders.objects = []
            return
        arguments = self.shape_params.outline_arguments()
        for key, value in self._shape_gaps(gaps, arguments).items():
            if value is None:
                continue
            symbol, unit, _ = gaps.GAP_METADATA[key]
            start, end = (value - 1, value + 1) if unit == "m" else (-0.1, 1)
            scale = GAP_SCALE[unit]
            slider = FormattedEditableFloatSlider(
                # Short, as in the metrics table, which names it in full on hover
                name=f"{symbol} [{unit}]",
                value=value * scale,
                start=start * scale,
                end=end * scale,
                step=0.005 * scale,
                width=INPUT_WIDTH,
            )
            slider.param.watch(self._fit_to_gaps, "value")
            # Only once let go, as it may miss on the way
            slider.param.watch(self._warn_missed_gaps, "value_throttled")
            self._sliders[key] = slider
        self.sliders.objects = list(self._sliders.values())

    def _gap_targets(self, gaps):
        """The gaps of the gap sliders, in metres by name."""
        return {
            key: slider.value / GAP_SCALE[gaps.GAP_METADATA[key][1]]
            for key, slider in self._sliders.items()
        }

    def _fit_to_gaps(self, event=None):
        """Set the shape parameters to those whose gaps come closest to the gap
        sliders."""
        gaps = MACHINE_GAPS[self.nice_settings.machine_preset]
        targets = self._gap_targets(gaps)
        ranges = {
            name: self.shape_params.param[name].softbounds for name in self.gap_params
        }
        fitted = gaps.fit_shape(self.shape_params.outline_arguments(), targets, ranges)
        self.shape_params.param.update(
            **{name: fitted[name] for name in self.gap_params}
        )

    def _warn_missed_gaps(self, event=None):
        """Warn when the shape misses the gap sliders."""
        gaps = MACHINE_GAPS[self.nice_settings.machine_preset]
        targets = self._gap_targets(gaps)
        reached = self._shape_gaps(gaps, self.shape_params.outline_arguments())
        missed = {
            key: np.inf if reached.get(key) is None else abs(reached[key] - target)
            for key, target in targets.items()
        }
        worst = max(missed, key=missed.get)
        if missed[worst] > self.shape_params.FIT_TOLERANCE:
            symbol = gaps.GAP_METADATA[worst][0]
            by = "" if np.isinf(missed[worst]) else f" by {missed[worst] * 100:.1f} cm"
            pn.state.notifications.warning(f"The closest shape misses {symbol}{by}")

    def __panel__(self):
        return self.panel
